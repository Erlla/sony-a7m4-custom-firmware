// Float64 mirror of the calibrated color bridge and trilinear camera-grid model.
// No physical BIONZ stage order is implied by this host-side empirical operator.
extern "C" __device__ double __nv_exp(double);
extern "C" __device__ double __nv_tanh(double);
__device__ double clamp_code(double v) { return v<0?0:(v>255?255:v); }
__device__ double clamp_unit(double v) { return v<0?0:(v>1?1:v); }

extern "C" __global__ void bake_color(int size,int components,const int*offsets,
    const double*inverse_variance,const double*limits,const double*centers,const double*weights,
    const int*features,const double*response,const double*grid,int grid_active,double*output) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=size*size*size)return;
    double input[3]={double(i/(size*size))*255/(size-1),double((i/size)%size)*255/(size-1),double(i%size)*255/(size-1)};
    double x[3]={input[0],input[1],input[2]};
    for(int c=0;c<components;++c) {
        double sum[3]={0,0,0};
        for(int n=offsets[c];n<offsets[c+1];++n) {
            double r=input[0]/255-centers[n*3],g=input[1]/255-centers[n*3+1],b=input[2]/255-centers[n*3+2];
            double v=__nv_exp(-(r*r+g*g+b*b)*inverse_variance[c]);
            for(int k=0;k<3;++k)sum[k]+=v*weights[n*3+k];
        }
        for(int k=0;k<3;++k)x[k]+=limits[c]>0?limits[c]*__nv_tanh(sum[k]/limits[c]):sum[k];
    }
    for(int k=0;k<3;++k)x[k]=clamp_code(x[k]);
    if(grid_active) {
        double r=x[0]/127.5-1,g=x[1]/127.5-1,b=x[2]/127.5-1;
        double f[10]={1,r,g,b,r*r,r*g,r*b,g*g,g*b,b*b};
        double jac[3][3],u[3];
        for(int c=0;c<3;++c) {
            double v[4]={0,0,0,0};
            for(int n=0;n<features[c];++n)for(int k=0;k<4;++k)v[k]+=f[n]*response[(c*10+n)*4+k];
            for(int k=0;k<3;++k)jac[c][k]=v[k];
            u[c]=clamp_unit(v[3]);
        }
        int dims[3]={4,8,8},lo[3];double frac[3];
        for(int k=0;k<3;++k){double pos=u[k]*dims[k];lo[k]=int(pos);if(lo[k]>=dims[k])lo[k]=dims[k]-1;frac[k]=pos-lo[k];}
        for(int c=0;c<3;++c) {
            double amplitude=0;
            for(int a=0;a<2;++a)for(int b0=0;b0<2;++b0)for(int d=0;d<2;++d) {
                double w=(a?frac[0]:1-frac[0])*(b0?frac[1]:1-frac[1])*(d?frac[2]:1-frac[2]);
                amplitude+=w*grid[c*405+(lo[0]+a)*81+(lo[1]+b0)*9+lo[2]+d];
            }
            for(int k=0;k<3;++k)x[k]+=jac[c][k]*amplitude;
        }
    }
    for(int k=0;k<3;++k)output[i*3+k]=clamp_code(x[k]);
}

extern "C" __global__ void render_color(const unsigned short*source,unsigned short*output,
    int pixels,int size,const double*table) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=pixels)return;
    int lo[3];double frac[3];
    for(int k=0;k<3;++k) {
        double pos=double(source[i*3+k])*(size-1)/65535;
        lo[k]=int(pos);if(lo[k]>=size-1)lo[k]=size-2;frac[k]=pos-lo[k];
    }
    double value[3]={0,0,0};
    for(int a=0;a<2;++a)for(int b=0;b<2;++b)for(int c=0;c<2;++c) {
        double weight=(a?frac[0]:1-frac[0])*(b?frac[1]:1-frac[1])*(c?frac[2]:1-frac[2]);
        int at=((lo[0]+a)*size*size+(lo[1]+b)*size+lo[2]+c)*3;
        for(int k=0;k<3;++k)value[k]+=weight*table[at+k];
    }
    for(int k=0;k<3;++k)output[i*3+k]=(unsigned short)__double2int_rn(clamp_code(value[k])*257);
}
