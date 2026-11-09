"""Small Windows CUDA Driver/NVRTC renderer; PyTorch remains the training API."""
from pathlib import Path
from contextlib import contextmanager
import atexit,ctypes as C,hashlib,json,os,shutil
from support import np,HERE


def compiler_path():
    nvcc=shutil.which('nvcc')
    if os.name!='nt' or not nvcc:return None
    root=Path(nvcc).resolve().parents[1]
    for folder in (root/'bin/x64',root/'bin'):
        files=sorted(folder.glob('nvrtc64*.dll'))
        if files:return files[-1]
    return None


class Runtime:
    def __init__(self):
        self.driver=C.WinDLL('nvcuda.dll')
        specs={
            'cuInit':[C.c_uint],'cuDeviceGet':[C.POINTER(C.c_int),C.c_int],
            'cuDeviceGetAttribute':[C.POINTER(C.c_int),C.c_int,C.c_int],
            'cuDriverGetVersion':[C.POINTER(C.c_int)],
            'cuDeviceGetName':[C.c_char_p,C.c_int,C.c_int],
            'cuDevicePrimaryCtxRetain':[C.POINTER(C.c_void_p),C.c_int],
            'cuDevicePrimaryCtxRelease_v2':[C.c_int],'cuCtxSetCurrent':[C.c_void_p],
            'cuModuleLoadData':[C.POINTER(C.c_void_p),C.c_void_p],
            'cuModuleGetFunction':[C.POINTER(C.c_void_p),C.c_void_p,C.c_char_p],
            'cuModuleUnload':[C.c_void_p],
            'cuMemAlloc_v2':[C.POINTER(C.c_uint64),C.c_size_t],
            'cuMemFree_v2':[C.c_uint64],
            'cuMemcpyHtoD_v2':[C.c_uint64,C.c_void_p,C.c_size_t],
            'cuMemcpyDtoH_v2':[C.c_void_p,C.c_uint64,C.c_size_t],
            'cuCtxSynchronize':[],
            'cuLaunchKernel':[C.c_void_p,*([C.c_uint]*7),C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_void_p)]}
        for name,types in specs.items():getattr(self.driver,name).argtypes=types
        self.check(self.driver.cuInit(0));device=C.c_int();self.check(self.driver.cuDeviceGet(C.byref(device),0));self.device=device.value
        self.context=C.c_void_p();self.check(self.driver.cuDevicePrimaryCtxRetain(C.byref(self.context),self.device))
        self.check(self.driver.cuCtxSetCurrent(self.context))
        major=C.c_int();minor=C.c_int();version=C.c_int()
        self.check(self.driver.cuDeviceGetAttribute(C.byref(major),75,self.device))
        self.check(self.driver.cuDeviceGetAttribute(C.byref(minor),76,self.device))
        self.check(self.driver.cuDriverGetVersion(C.byref(version)))
        name=C.create_string_buffer(256);self.check(self.driver.cuDeviceGetName(name,len(name),self.device))
        self.identity=dict(device=name.value.decode(),compute=f'{major.value}.{minor.value}',driver_version=version.value)
        path=compiler_path();self.dll_directory=os.add_dll_directory(str(path.parent));nvrtc=C.WinDLL(str(path))
        n_major=C.c_int();n_minor=C.c_int();nvrtc.nvrtcVersion(C.byref(n_major),C.byref(n_minor))
        self.identity['NVRTC_version']=[n_major.value,n_minor.value]
        source=(HERE/'m4_pixels.cu').read_bytes()
        options=[f'--gpu-architecture=sm_{major.value}{minor.value}','--std=c++14','--fmad=false']
        digest=hashlib.sha256(source+json.dumps([options,self.identity['NVRTC_version']]).encode()).hexdigest()
        cache=HERE/'_local/cuda-kernels';cache.mkdir(parents=True,exist_ok=True);file=cache/(digest+'.cubin')
        if not file.exists():file.write_bytes(self.compile(nvrtc,source,options))
        binary_bytes=file.read_bytes();binary=C.create_string_buffer(binary_bytes);self.module=C.c_void_p()
        self.check(self.driver.cuModuleLoadData(C.byref(self.module),binary))
        self.functions={}
        for function in ('bake_color','render_color'):
            handle=C.c_void_p();self.check(self.driver.cuModuleGetFunction(C.byref(handle),self.module,function.encode()))
            self.functions[function]=handle
        self.identity.update(kernel_source_sha256=hashlib.sha256(source).hexdigest(),compile_key=digest,
            cubin_sha256=hashlib.sha256(binary_bytes).hexdigest())
        atexit.register(self.close)

    @staticmethod
    def check(code):
        if code:raise RuntimeError(f'CUDA Driver error {code}')

    @staticmethod
    def compile(nvrtc,source,options):
        nvrtc.nvrtcCreateProgram.argtypes=[C.POINTER(C.c_void_p),C.c_char_p,C.c_char_p,C.c_int,C.c_void_p,C.c_void_p]
        nvrtc.nvrtcCompileProgram.argtypes=[C.c_void_p,C.c_int,C.POINTER(C.c_char_p)]
        for name in ('nvrtcGetProgramLogSize','nvrtcGetCUBINSize'):getattr(nvrtc,name).argtypes=[C.c_void_p,C.POINTER(C.c_size_t)]
        for name in ('nvrtcGetProgramLog','nvrtcGetCUBIN'):getattr(nvrtc,name).argtypes=[C.c_void_p,C.c_void_p]
        nvrtc.nvrtcDestroyProgram.argtypes=[C.POINTER(C.c_void_p)]
        program=C.c_void_p();code=nvrtc.nvrtcCreateProgram(C.byref(program),source,b'm4_pixels.cu',0,None,None)
        if code:raise RuntimeError(f'NVRTC create error {code}')
        try:
            encoded=(C.c_char_p*len(options))(*[o.encode()for o in options])
            code=nvrtc.nvrtcCompileProgram(program,len(options),encoded)
            if code:
                size=C.c_size_t();nvrtc.nvrtcGetProgramLogSize(program,C.byref(size));log=C.create_string_buffer(size.value)
                nvrtc.nvrtcGetProgramLog(program,log);raise RuntimeError(log.value.decode())
            size=C.c_size_t();nvrtc.nvrtcGetCUBINSize(program,C.byref(size));binary=C.create_string_buffer(size.value)
            code=nvrtc.nvrtcGetCUBIN(program,binary)
            if code:raise RuntimeError(f'NVRTC cubin error {code}')
            return binary.raw
        finally:nvrtc.nvrtcDestroyProgram(C.byref(program))

    def close(self):
        self.driver.cuModuleUnload(self.module)
        self.driver.cuDevicePrimaryCtxRelease_v2(self.device)

    @contextmanager
    def buffers(self):
        allocated=[]
        def allocate(array=None,size=None):
            if array is not None:array=np.ascontiguousarray(array);size=array.nbytes
            ptr=C.c_uint64();self.check(self.driver.cuMemAlloc_v2(C.byref(ptr),max(size,8)));allocated.append(ptr)
            if array is not None:self.check(self.driver.cuMemcpyHtoD_v2(ptr,array.ctypes.data,array.nbytes))
            return ptr
        try:yield allocate
        finally:
            for ptr in reversed(allocated):self.driver.cuMemFree_v2(ptr)

    def launch(self,name,count,arguments):
        pointers=(C.c_void_p*len(arguments))(*[C.cast(C.byref(arg),C.c_void_p)for arg in arguments])
        self.check(self.driver.cuLaunchKernel(self.functions[name],(count+255)//256,1,1,256,1,1,0,None,pointers,None))
        self.check(self.driver.cuCtxSynchronize())

    def bake(self,grid,model,calibration,size,anchor):
        def parts(value):
            if value is None:return []
            if 'components'in value:return [part for child in value['components']for part in parts(child)]
            return [value]
        components=parts(calibration);offsets=[0];centers=[];weights=[];inverse=[];limits=[]
        for value in components:
            centers.extend(value['centers']);weights.extend(value['weights']);offsets.append(len(centers))
            inverse.append(1/(2*value['width']**2));limits.append(value.get('limit_RGB',0))
        response=np.zeros((3,10,4));features=np.zeros(3,np.int32)
        for i,channel in enumerate(model['channels']):
            values=np.asarray(channel['weights']);response[i,:len(values)]=values;features[i]=len(values)
        delta=np.asarray(grid,float)-(np.zeros_like(grid)if anchor is None else np.asarray(anchor))
        out=np.empty((size,size,size,3),np.float64)
        array=lambda value,dtype=np.float64:np.asarray(value if len(value)else [0],dtype)
        with self.buffers()as alloc:
            args=[C.c_int(size),C.c_int(len(components)),alloc(array(offsets,np.int32)),
                alloc(array(inverse)),alloc(array(limits)),alloc(array(centers)),alloc(array(weights)),
                alloc(features),alloc(response),alloc(delta),C.c_int(int(np.any(delta))),alloc(size=out.nbytes)]
            self.launch('bake_color',size**3,args)
            self.check(self.driver.cuMemcpyDtoH_v2(out.ctypes.data,args[-1],out.nbytes))
        return out

    def image(self,source,output,table):
        import tifffile
        from PIL import ImageCms
        src=tifffile.memmap(source);icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        dest=tifffile.memmap(output,shape=src.shape,dtype='<u2',photometric='rgb',metadata=None,
            extratags=[(34675,'B',len(icc),icc,False)])
        with self.buffers()as alloc:
            args=[alloc(src),alloc(size=dest.nbytes),C.c_int(src.shape[0]*src.shape[1]),C.c_int(len(table)),alloc(np.asarray(table,np.float64))]
            self.launch('render_color',src.shape[0]*src.shape[1],args)
            self.check(self.driver.cuMemcpyDtoH_v2(dest.ctypes.data,args[1],dest.nbytes))
        dest.flush()


_runtime=None
def runtime():
    global _runtime
    if _runtime is None:_runtime=Runtime()
    return _runtime
