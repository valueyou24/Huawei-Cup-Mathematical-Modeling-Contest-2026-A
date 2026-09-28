"""Generate six dependency-light PNG figures from the 500-run result table."""
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]; CSV=ROOT/"analysis_results"/"full"/"all_results.csv"; OUT=ROOT/"paper_assets"; W,H=1800,1050
FONT=Path(r"C:\Windows\Fonts\msyh.ttc")
def ft(n,bold=False):
    p=Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else FONT
    return ImageFont.truetype(str(p if p.exists() else FONT),n)
def canvas(title,xlabel,ylabel):
    im=Image.new("RGB",(W,H),"white"); d=ImageDraw.Draw(im); d.text((W//2,45),title,font=ft(44,1),fill="#222",anchor="ma")
    L,T,R,B=210,150,1650,875; d.line((L,T,L,B,R,B),fill="#333",width=4); d.text(((L+R)//2,980),xlabel,font=ft(30),fill="#222",anchor="mm"); d.text((L,T-18),ylabel,font=ft(25),fill="#222",anchor="ls")
    return im,d,(L,T,R,B)
def axes(d,b,xs,ys,xlabels=None):
    L,T,R,B=b; xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys); pad=.06*(ymax-ymin or 1); ymin-=pad; ymax+=pad
    X=lambda x:L+(x-xmin)/(xmax-xmin or 1)*(R-L); Y=lambda y:B-(y-ymin)/(ymax-ymin)*(B-T)
    for i in range(6):
        v=ymin+i*(ymax-ymin)/5; yy=Y(v); d.line((L,yy,R,yy),fill="#ddd",width=2); d.text((L-18,yy),f"{v:.2f}",font=ft(22),fill="#444",anchor="rm")
    for i,x in enumerate(xs): d.text((X(x),B+18),xlabels[i] if xlabels is not None else str(x),font=ft(23),fill="#333",anchor="ma")
    return X,Y
def save(im,name): im.save(OUT/name,dpi=(300,300),optimize=True)
def lineplot(df):
    g=df.groupby("cores")[["p1_speedup","p2_speedup"]].mean(); x=g.index.to_numpy(); im,d,b=canvas("多核调度平均加速比","NPU 核数","相对单核平均加速比"); X,Y=axes(d,b,x,np.r_[g.values.ravel(),1],x.astype(str)); d.line((b[0],Y(1),b[2],Y(1)),fill="#888",width=3)
    for col,color,label,y0 in [("p1_speedup","#1769aa","场景A（问题1）",170),("p2_speedup","#d97706","场景B（问题2）",215)]:
        pts=[(X(a),Y(v)) for a,v in zip(x,g[col])]; d.line(pts,fill=color,width=7)
        for p in pts:d.ellipse((p[0]-9,p[1]-9,p[0]+9,p[1]+9),fill=color)
        d.line((1260,y0,1320,y0),fill=color,width=7); d.text((1340,y0),label,font=ft(24),fill="#222",anchor="lm")
    save(im,"fig01_mean_speedup.png")
def boxplot(df):
    im,d,b=canvas("问题2加速比分布","NPU 核数","问题2加速比"); groups=[df.loc[df.cores==c,"p2_speedup"].to_numpy() for c in range(2,6)]; X,Y=axes(d,b,[2,3,4,5],np.r_[np.concatenate(groups),1],["2","3","4","5"]); d.line((b[0],Y(1),b[2],Y(1)),fill="#b23a48",width=3)
    for c,a in zip(range(2,6),groups):
        q1,med,q3=np.quantile(a,[.25,.5,.75]); lo,hi=np.min(a),np.max(a); xx=X(c); bw=90; d.line((xx,Y(lo),xx,Y(hi)),fill="#1769aa",width=4); d.rectangle((xx-bw,Y(q3),xx+bw,Y(q1)),fill="#bde0fe",outline="#1769aa",width=4); d.line((xx-bw,Y(med),xx+bw,Y(med)),fill="#d97706",width=5)
    save(im,"fig02_p2_distribution.png")
def bars(df):
    g=df.groupby("cores")[["p1_added_copy_bytes","p2_added_copy_bytes"]].mean()/2**20; x=g.index.to_numpy(); im,d,b=canvas("分核引入的平均额外搬运量","NPU 核数","平均新增搬运量 / MiB"); X,Y=axes(d,b,x,np.r_[g.values.ravel(),0],x.astype(str)); bw=55
    for c,a,z in zip(x,g.p1_added_copy_bytes,g.p2_added_copy_bytes): xx=X(c); d.rectangle((xx-bw,Y(a),xx-5,Y(0)),fill="#1769aa"); d.rectangle((xx+5,Y(z),xx+bw,Y(0)),fill="#d97706")
    d.rectangle((1300,165,1340,195),fill="#1769aa");d.text((1360,180),"问题1",font=ft(24),fill="#222",anchor="lm");d.rectangle((1300,210,1340,240),fill="#d97706");d.text((1360,225),"问题2",font=ft(24),fill="#222",anchor="lm");save(im,"fig03_copy_overhead.png")
def l2plot(df):
    g=df.groupby("cores")[["p3_vs_no_l2_speedup","p3_cache_hit_rate"]].mean(); x=g.index.to_numpy(); hit=100*g.p3_cache_hit_rate.to_numpy(); im,d,b=canvas("只读 L2 Cache 的收益与命中率","NPU 核数","L2 相对无 L2 加速比（蓝）"); X,Y=axes(d,b,x,np.r_[g.p3_vs_no_l2_speedup,1],x.astype(str)); ymax=max(hit)*1.1; Y2=lambda v:b[3]-v/ymax*(b[3]-b[1]); d.line([(X(a),Y(v)) for a,v in zip(x,g.p3_vs_no_l2_speedup)],fill="#1769aa",width=7); d.line([(X(a),Y2(v)) for a,v in zip(x,hit)],fill="#d97706",width=7)
    for i in range(6): v=i*ymax/5; d.text((b[2]+18,Y2(v)),f"{v:.1f}%",font=ft(22),fill="#d97706",anchor="lm")
    d.text((1740,(b[1]+b[3])//2),"字节命中率（橙）",font=ft(24),fill="#d97706",anchor="mm");save(im,"fig04_l2_effect.png")
def scatter(df):
    a=df[df.cores==5]; x=np.log10(a.ops+a.tensors+a.edges).to_numpy(); y=a.p2_speedup.to_numpy(); c=(100*a.p3_cache_hit_rate).to_numpy(); im,d,b=canvas("图规模、5核加速比与 L2 命中率","图规模 log10(Op+Tensor+Edge)","5核问题2加速比"); X,Y=axes(d,b,[x.min(),x.max()],np.r_[y,1],[f"{x.min():.1f}",f"{x.max():.1f}"]); d.line((b[0],Y(1),b[2],Y(1)),fill="#888",width=3)
    for xx,yy,cc in zip(x,y,c): t=min(1,cc/35); color=(int(45+200*t),int(120+80*(1-t)),int(190-120*t)); px,py=X(xx),Y(yy); d.ellipse((px-8,py-8,px+8,py+8),fill=color)
    d.text((1200,170),"颜色由蓝到黄表示命中率升高",font=ft(24),fill="#333");save(im,"fig05_size_speedup.png")
def flow():
    im=Image.new("RGB",(2200,620),"white"); d=ImageDraw.Draw(im); d.text((1100,45),"求解算法总体流程",font=ft(44,1),fill="#222",anchor="ma"); labs=["解析 Op–Tensor 图","压缩 Op DAG\n计算通信权重","关键路径优先\n拓扑排序","均衡聚合\n形成子图","通信感知\n列表调度","官方仿真\n校验计时"]
    for i,s in enumerate(labs):
        x=70+i*355; d.rounded_rectangle((x,205,x+270,430),radius=24,fill="#e8f1fb",outline="#1769aa",width=5); d.multiline_text((x+135,318),s,font=ft(29),fill="#222",anchor="mm",align="center",spacing=10)
        if i<5:d.line((x+280,318,x+342,318),fill="#555",width=5);d.polygon([(x+342,318),(x+320,305),(x+320,331)],fill="#555")
    save(im,"fig06_algorithm_flow.png")
def contact_sheet():
    names=["fig01_mean_speedup.png","fig02_p2_distribution.png","fig03_copy_overhead.png","fig04_l2_effect.png","fig05_size_speedup.png","fig06_algorithm_flow.png"]
    sheet=Image.new("RGB",(1600,1800),"#dddddd")
    for i,n in enumerate(names):
        im=Image.open(OUT/n).convert("RGB"); im.thumbnail((780,570)); x=(i%2)*800+(800-im.width)//2; y=(i//2)*600+(580-im.height)//2; sheet.paste(im,(x,y))
    sheet.save(OUT/"figure_contact_sheet.png",quality=92)
def main():
    OUT.mkdir(exist_ok=True); df=pd.read_csv(CSV,encoding="utf-8-sig"); lineplot(df);boxplot(df);bars(df);l2plot(df);scatter(df);flow();contact_sheet();print(f"generated 6 figures in {OUT}")
if __name__=="__main__":main()
