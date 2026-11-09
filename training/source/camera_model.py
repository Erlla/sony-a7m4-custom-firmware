"""Frozen M4 forward model: explicit native frontend, bridge and signed7 NN.

The trained camera response is fixed. Optimizers change native JSON parameters.
This implementation does not require a running Sony application or a camera.
"""
from pathlib import Path
import ctypes as C
import hashlib
import os
import sys
import numpy as np
import torch
import support as w
import pixel_bridge
from response_network import Response

torch.set_num_threads(1)
torch.backends.cuda.matmul.allow_tf32 = False


class CameraModel:
    def __init__(self, assets, sony_edit=None, srsettings=None, device='cuda'):
        self.assets = Path(assets).resolve()
        self.device = device
        self.path = self.assets / 'models/forward_model.json'
        contract = w.read(self.path)
        if contract.get('schema') != 'm4-camera-forward/2' or contract.get('backend') != 'edit-explicit':
            raise ValueError('Expected the supplied explicit M4 model')
        supplied = {'external:sony-edit': sony_edit or os.environ.get('SONY_EDIT_BINARY'),
                    'external:srsettings': srsettings or os.environ.get('M4_SRSETTINGS')}
        for key, row in contract['sources'].items():
            path = row['path']
            if path.startswith('external:'):
                if not supplied[path]:
                    raise FileNotFoundError('Supply local file for ' + path)
                row['path'] = str(Path(supplied[path]).resolve())
            elif path.startswith('code:'):
                row['path'] = str((w.HERE / path[5:]).resolve())
            else:
                row['path'] = str((self.path.parent / path).resolve())
            w.checked(row)
        self.contract = contract
        self.bridge_path = Path(contract['sources']['camera_bridge']['path'])
        bridge = w.read(self.bridge_path)
        for row in bridge['sources'].values():
            row['path'] = str((self.bridge_path.parent / row['path']).resolve())
            w.checked(row)
        sources = bridge['sources']
        self.anchor = w.fmt.parse(Path(sources['anchor_native']['path']).read_bytes())
        self.calibration = w.read(sources['color_bridge']['path'])
        self.grid_model = w.read(sources['grid_response']['path'])['model']
        self.anchor_grid = np.asarray(self.anchor['parameters']['grid']['photo']).reshape(3,5,9,9)
        checkpoint = torch.load(contract['sources']['grid_weights']['path'], map_location='cpu', weights_only=True)
        self.response = Response(checkpoint['seed'], checkpoint['width'])
        self.response.load_state_dict(checkpoint['state'])
        self.response.to(device).eval().requires_grad_(False)
        self.identity = self.configure()

    def configure(self):
        manifest = w.read(self.contract['sources']['upstream_manifest']['path'])
        upstream = w.HERE.parent / 'third_party'
        # Patch Windows libm paths in a writable per-run copy, retaining MIT source.
        runtime = Path(os.environ.get('M4_TRAINING_CACHE', self.assets/'_runtime')) / 'sonylook'
        runtime.mkdir(parents=True, exist_ok=True)
        patched = []
        for row in manifest['files']:
            source = upstream / row['path']
            w.checked(dict(row, path=str(source)))
            text = source.read_text('utf8')
            if os.name == 'nt' and '/usr/lib/libSystem.B.dylib' in text:
                text = text.replace('/usr/lib/libSystem.B.dylib', 'ucrtbase.dll')
                patched.append(row['path'])
            target = runtime / source.name
            if not target.exists() or target.read_text('utf8') != text:
                target.write_text(text, encoding='utf8', newline='\n')
        os.environ['SONY_EDIT_BINARY'] = self.contract['sources']['edit_constants']['path']
        os.environ['SONY_EDIT_RESOURCES'] = str(Path(self.contract['sources']['srsettings']['path']).parent)
        os.environ['SONYLOOK_CACHE_DIR'] = str(runtime.parent/'table-cache')
        sys.path.insert(0, str(runtime))
        w.raw_module()
        import edit_binary
        actual = hashlib.sha256(edit_binary.arm64_slice()).hexdigest()
        if actual != self.contract['edit_arm64_sha256']:
            raise ValueError('Unsupported Edit ARM64 slice')
        return dict(upstream_commit=manifest['commit'], edit_arm64_sha256=actual,
                    model_math_contract=self.contract['original_math_contract_sha256'],
                    platform_patches=patched, running_Sony_process=False, camera_access=False)

    def forward(self, rgb, grid):
        """Differentiable post-native operator; RGB in 0..255, grid in native units."""
        rgb = torch.as_tensor(rgb, dtype=torch.float64, device=self.device)
        zero = torch.zeros((3,5,9,9), dtype=rgb.dtype, device=rgb.device)
        base = pixel_bridge.torch_transform(rgb, zero, self.grid_model, self.calibration,
                                           self.anchor_grid).to(torch.float32)
        grid = torch.as_tensor(grid, dtype=torch.float32, device=rgb.device).reshape(1,3,5,9,9)
        return self.response(base[None], grid)[0][0]

    def bake(self, native, size=129):
        """The formal table keeps the established node order and 32768 chunk size."""
        grid = np.asarray(native['parameters']['grid']['photo']).reshape(3,5,9,9)
        axis = np.linspace(0,255,size)
        samples = np.stack(np.meshgrid(axis,axis,axis,indexing='ij'),-1).reshape(-1,3)
        table = np.empty_like(samples)
        with torch.no_grad():
            for start in range(0,len(samples),32768):
                table[start:start+32768] = self.forward(samples[start:start+32768],grid).cpu().numpy()
        return table.reshape(size,size,size,3)

    def sample(self, native16, table):
        """Formal RGB16 output. CPU and the retained CUDA kernel use float64."""
        values = np.ascontiguousarray(native16,dtype='<u2').reshape(-1,3)
        if self.device.startswith('cuda'):
            import cuda_pixels
            if cuda_pixels.compiler_path() is None:
                raise RuntimeError('Formal CUDA RGB16 replay requires CUDA Toolkit/NVRTC; use --device cpu otherwise')
            runtime = cuda_pixels.runtime()
            out = np.empty_like(values)
            with runtime.buffers() as alloc:
                args = [alloc(values),alloc(size=out.nbytes),C.c_int(len(values)),C.c_int(len(table)),
                        alloc(np.asarray(table,np.float64))]
                runtime.launch('render_color',len(values),args)
                runtime.check(runtime.driver.cuMemcpyDtoH_v2(out.ctypes.data,args[1],out.nbytes))
            return out
        pos=values.astype(np.float64)*(len(table)-1)/65535
        low=np.minimum(pos.astype(int),len(table)-2); fraction=pos-low
        out=np.zeros(values.shape,np.float64)
        for corner in np.ndindex(2,2,2):
            c=np.asarray(corner); at=low+c
            weight=np.prod(np.where(c,fraction,1-fraction),axis=1)
            out+=weight[:,None]*table[at[:,0],at[:,1],at[:,2]]
        return np.rint(np.clip(out,0,255)*257).astype(np.uint16)

    def chart_native(self, native):
        """Actual Sony ARW CFA-derived interiors; design RGB is never the input."""
        dataset=w.read(self.assets/'charts/dataset.json')
        raw=self.assets/dataset['raw_files']['arw']['path']
        w.checked(dict(dataset['raw_files']['arw'],path=str(raw)))
        inputs=np.load(self.assets/'charts/sony_input.npz',allow_pickle=False)
        import native_frontend as E
        import sony_render as R
        with E.selected_record(raw,native,'endpoint0-legacy','fixed'):
            look=R.Look('Standard',R.load_looks(str(raw)),fade=0,use_rust=False)
            result=look.render(inputs['front'][:,None,:],pointwise=True,
                               sscs=dataset['captured_context']['sscs'],strip=0)[:,0]
        return result.astype(np.uint16)<<2

    def check_defaults(self,native):
        if native['defaults'] != self.anchor['defaults']:
            raise ValueError('This model requires the calibrated menu defaults; independent slider mapping is not qualified')
