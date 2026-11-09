import torch

def lab(rgb):
    x=rgb/255;linear=torch.where(x<=.04045,x/12.92,((x+.055)/1.055).clamp_min(1e-20)**2.4)
    mat=x.new_tensor([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]])
    v=(linear@mat.T)/x.new_tensor([.95047,1,1.08883]);d=6/29
    f=torch.where(v>d**3,v.clamp_min(1e-20)**(1/3),v/(3*d*d)+4/29)
    return torch.stack((116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])),dim=1)


def de00(a,b):
    L1,a1,b1=a.unbind(-1);L2,a2,b2=b.unbind(-1)
    norm=lambda a,b:(a*a+b*b+1e-24).sqrt()
    c1=norm(a1,b1);c2=norm(a2,b2);cb=(c1+c2)/2
    G=.5*(1-(cb**7/(cb**7+25**7)).sqrt());ap1=(1+G)*a1;ap2=(1+G)*a2
    cp1=norm(ap1,b1);cp2=norm(ap2,b2)
    hp1=torch.remainder(torch.atan2(b1,ap1),2*torch.pi);hp2=torch.remainder(torch.atan2(b2,ap2),2*torch.pi)
    dl=L2-L1;dc=cp2-cp1;dh=hp2-hp1;zero=(cp1*cp2)<1e-20
    dh=torch.where(zero,0.,torch.where(dh>torch.pi,dh-2*torch.pi,torch.where(dh<-torch.pi,dh+2*torch.pi,dh)))
    dH=2*(cp1*cp2).sqrt()*torch.sin(dh/2);lb=(L1+L2)/2;cp=(cp1+cp2)/2
    hp=torch.where(zero,hp1+hp2,torch.where(abs(hp1-hp2)<=torch.pi,(hp1+hp2)/2,
        torch.where(hp1+hp2<2*torch.pi,(hp1+hp2+2*torch.pi)/2,(hp1+hp2-2*torch.pi)/2)))
    T=1-.17*torch.cos(hp-torch.pi/6)+.24*torch.cos(2*hp)+.32*torch.cos(3*hp+torch.pi/30)-.20*torch.cos(4*hp-63*torch.pi/180)
    sl=1+.015*(lb-50)**2/torch.sqrt(20+(lb-50)**2);sc=1+.045*cp;sh=1+.015*cp*T
    rt=-2*torch.sqrt(cp**7/(cp**7+25**7))*torch.sin(torch.pi/3*torch.exp(-((hp*180/torch.pi-275)/25)**2))
    return ((dl/sl)**2+(dc/sc)**2+(dH/sh)**2+rt*(dc/sc)*(dH/sh)).clamp_min(1e-24).sqrt()
