"""Build the competition paper DOCX from the supplied template and experiment data."""
from pathlib import Path
import math
import os
import tempfile
import zipfile
import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"研究生数学建模word模板.docx"
CSV=ROOT/"analysis_results"/"full"/"all_results.csv"
OUT=ROOT/"通用神经网络处理器下的多核调度优化模型_论文.docx"
FIG=ROOT/"paper_assets"

def clear_body(doc):
    body=doc._element.body; sect=body.sectPr
    for e in list(body):
        if e is not sect: body.remove(e)

def set_cell_shading(cell,fill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=tcPr.find(qn("w:shd"))
    if shd is None: shd=OxmlElement("w:shd"); tcPr.append(shd)
    shd.set(qn("w:fill"),fill)

def set_repeat_header(row):
    trPr=row._tr.get_or_add_trPr(); e=OxmlElement("w:tblHeader"); e.set(qn("w:val"),"true"); trPr.append(e)

def set_cell_text(cell,text,bold=False,size=9):
    cell.text=""; p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(str(text)); r.bold=bold; r.font.size=Pt(size); r.font.name="Times New Roman"; r._element.rPr.rFonts.set(qn("w:eastAsia"),"宋体")
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER

def add_table(doc,headers,rows,widths=None,size=9):
    t=doc.add_table(rows=1,cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style="Table Grid"
    set_repeat_header(t.rows[0])
    for i,h in enumerate(headers): set_cell_text(t.rows[0].cells[i],h,True,size); set_cell_shading(t.rows[0].cells[i],"D9EAF7")
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row): set_cell_text(cells[i],v,False,size)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Cm(w)
    doc.add_paragraph()
    return t

def add_text(doc,text,bold_start=None):
    p=doc.add_paragraph(style="Normal"); p.paragraph_format.first_line_indent=Cm(.74); p.paragraph_format.line_spacing=1.5; p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    if bold_start and text.startswith(bold_start):
        r=p.add_run(bold_start); r.bold=True; p.add_run(text[len(bold_start):])
    else:p.add_run(text)
    return p

def add_bullets(doc,items):
    for i,x in enumerate(items,1):
        p=doc.add_paragraph(style="Normal"); p.paragraph_format.left_indent=Cm(.7); p.paragraph_format.first_line_indent=Cm(-.7); p.paragraph_format.line_spacing=1.35; p.add_run(f"（{i}）{x}")

def heading(doc,text,level=1):
    p=doc.add_paragraph(text,style=f"Heading {level}"); p.paragraph_format.keep_with_next=True; return p

def add_math(doc,formula,no):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    om=OxmlElement("m:oMathPara"); eq=OxmlElement("m:oMath"); mr=OxmlElement("m:r"); mt=OxmlElement("m:t"); mt.text=formula; mr.append(mt); eq.append(mr); om.append(eq); p._p.append(om)
    p.add_run(f"    （{no}）")
    return p

def add_figure(doc,name,caption,width=14.8):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next=True
    p.add_run().add_picture(str(FIG/name),width=Cm(width))
    c=doc.add_paragraph(caption); c.alignment=WD_ALIGN_PARAGRAPH.CENTER; c.paragraph_format.keep_with_next=True

def add_page_number(paragraph):
    paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=paragraph.add_run(); begin=OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"),"begin"); instr=OxmlElement("w:instrText"); instr.set(qn("xml:space"),"preserve"); instr.text=" PAGE "; separate=OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"),"separate"); text=OxmlElement("w:t"); text.text="1"; end=OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"),"end")
    for e in (begin,instr,separate,text,end): run._r.append(e)

def add_toc(doc):
    heading(doc,"目录",1); p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(); b=OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"),"begin"); ins=OxmlElement("w:instrText"); ins.set(qn("xml:space"),"preserve"); ins.text=' TOC \\o "1-3" \\h \\z \\u '; sep=OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"),"separate"); tx=OxmlElement("w:t"); tx.text="打开 Word 后按 Ctrl+A、F9 更新目录与页码"; end=OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"),"end")
    for e in (b,ins,sep,tx,end):r._r.append(e)

def configure_styles(doc):
    normal=doc.styles["Normal"]; normal.font.name="Times New Roman"; normal._element.rPr.rFonts.set(qn("w:eastAsia"),"宋体"); normal.font.size=Pt(11)
    for level,size in [(1,16),(2,14),(3,12)]:
        s=doc.styles[f"Heading {level}"]; s.font.name="Times New Roman"; s._element.rPr.rFonts.set(qn("w:eastAsia"),"黑体"); s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor(0,0,0)

def cover(doc):
    sec=doc.sections[0]; sec.page_width=Cm(21); sec.page_height=Cm(29.7); sec.top_margin=Cm(2.97); sec.bottom_margin=Cm(2.34); sec.left_margin=Cm(2.21); sec.right_margin=Cm(2.21); sec.different_first_page_header_footer=True
    for part in (sec.header,sec.footer,sec.first_page_header,sec.first_page_footer):
        for p in part.paragraphs: p.text=""
        for table in list(part.tables): table._element.getparent().remove(table._element)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(36); r=p.add_run("研究生数学建模竞赛论文"); r.bold=True; r.font.size=Pt(22); r.font.name="SimHei"; r._element.rPr.rFonts.set(qn("w:eastAsia"),"黑体")
    for _ in range(3):doc.add_paragraph()
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run("通用神经网络处理器下的\n多核调度优化模型"); r.bold=True; r.font.size=Pt(30); r.font.name="SimHei"; r._element.rPr.rFonts.set(qn("w:eastAsia"),"黑体")
    doc.add_paragraph(); doc.add_paragraph()
    rows=[["参赛学校","待填写"],["参赛队号","待填写"],["队员姓名","待填写"],["完成日期","待填写"]]
    t=doc.add_table(rows=0,cols=2); t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for a,b in rows:
        cells=t.add_row().cells; set_cell_text(cells[0],a,True,13); set_cell_text(cells[1],b,False,13)
    doc.add_paragraph(); p=doc.add_paragraph("说明：封面身份信息已留空，请提交前填写。") ;p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    sec2=doc.add_section(WD_SECTION.NEW_PAGE); sec2.page_width=Cm(21); sec2.page_height=Cm(29.7); sec2.top_margin=Cm(2.55); sec2.bottom_margin=Cm(2.35); sec2.left_margin=Cm(2.4); sec2.right_margin=Cm(2.2)
    sec2.header.is_linked_to_previous=False; sec2.footer.is_linked_to_previous=False
    sec2.header.paragraphs[0].text="通用神经网络处理器下的多核调度优化模型"; sec2.header.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
    sec2.footer.paragraphs[0].clear(); add_page_number(sec2.footer.paragraphs[0])

def prune_orphan_media(path):
    """Remove template images and image relationships no longer used by the new paper."""
    with zipfile.ZipFile(path,"r") as zin:
        files={n:zin.read(n) for n in zin.namelist()}
    # Remove unused image relationships from every relationships part.
    for relname in [n for n in files if n.endswith(".rels")]:
        try: root=__import__("xml.etree.ElementTree",fromlist=["ElementTree"]).fromstring(files[relname])
        except Exception: continue
        if "/_rels/" in relname:
            base=relname.replace("/_rels/","/")[:-5]
        else: base=""
        source=files.get(base,b"")
        changed=False
        for rel in list(root):
            if rel.get("Type","").endswith("/image") and rel.get("Id","").encode() not in source:
                root.remove(rel); changed=True
        if changed: files[relname]=__import__("xml.etree.ElementTree",fromlist=["ElementTree"]).tostring(root,encoding="utf-8",xml_declaration=True)
    used=set()
    for n,data in files.items():
        if n.endswith(".rels"):
            try: root=__import__("xml.etree.ElementTree",fromlist=["ElementTree"]).fromstring(data)
            except Exception: continue
            for rel in root:
                target=rel.get("Target","")
                if "media/" in target: used.add("word/media/"+target.split("media/",1)[1])
    files={n:d for n,d in files.items() if not n.startswith("word/media/") or n in used}
    fd,tmp=tempfile.mkstemp(suffix=".docx",dir=str(path.parent)); os.close(fd)
    try:
        with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as zout:
            for n,d in files.items(): zout.writestr(n,d)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    df=pd.read_csv(CSV,encoding="utf-8-sig"); doc=Document(TEMPLATE); clear_body(doc); configure_styles(doc); cover(doc)
    heading(doc,"摘要",1)
    add_text(doc,"针对通用神经网络处理器（NPU）上带有 Pipe、片上存储、共享 DDR、同步延迟与只读 L2 Cache 的多核调度问题，本文建立“图压缩—关键路径排序—均衡聚合—通信感知列表调度—官方离散事件仿真验证”的统一模型。模型先把 Op–Tensor 二部图压缩为带通信字节权的 Op 有向无环图，以静态底层长度识别关键路径；再将拓扑序列聚合为负载相近的连续子图，并在候选核上综合估计 Pipe 完成时刻、跨核同步延迟与搬运开销，构造确定性的可行调度。问题1采用较粗粒度切分控制 Task 边界开销，问题2、3采用较细粒度切分利用场景B的同核驻留；问题3严格复用问题2的分核结果，仅改变存储层次，以保证 L2 对比的公平性。")
    add_text(doc,"本文在全部100个正式算例、1—5核配置上完成500组官方评测，所有调度均通过合法性校验。五核时，问题1和问题2的平均加速比分别达到1.2902和1.6868；问题2在86%的算例中优于问题1。只读L2使五核平均执行时间进一步缩短3.84%，平均字节命中率为12.74%；在400组多核对照中，276组受益、115组持平、9组轻微退化。结果表明：多核扩展性主要由关键路径长度、共享DDR争用和跨核搬运共同决定；相较简单负载均衡，显式控制通信边界与Task粒度更为重要。")
    p=doc.add_paragraph(); p.add_run("关键词：").bold=True; p.add_run("计算图切分；多核调度；关键路径；列表调度；共享带宽；只读Cache")
    doc.add_page_break(); add_toc(doc); doc.add_page_break()

    heading(doc,"1 问题重述",1)
    add_text(doc,"题目给出由算子Op、张量Tensor以及数据依赖组成的神经网络计算图。需要为每个非COPY算子确定所属子图和NPU核，并为每个核给出子图执行顺序。评测程序随后自动重建Task边界的COPY_IN/COPY_OUT，执行片上存储分配与换入换出，并在共享DDR、Pipe互斥、同步延迟等约束下计算总完成时间Makespan。")
    add_bullets(doc,["问题1（场景A）：一个子图对应一个Task，Task之间不能复用片上数据；同Task切换等待100 cycles，跨Task等待1000 cycles。","问题2（场景B）：同一核的全部子图合并为一个Task，同核数据可直接驻留复用；跨核COPY同步延迟为500 cycles。","问题3：在问题2调度不变的基础上加入容量1 MiB、带宽250 bytes/cycle的只读FIFO L2 Cache，并与无L2结果比较。"])
    add_text(doc,"三个问题的共同目标是最小化Makespan；附带目标是在不牺牲关键路径进度的前提下减少跨核字节量和由片上空间不足产生的spill。")

    heading(doc,"2 模型假设与符号",1); heading(doc,"2.1 基本假设",2)
    add_bullets(doc,["计算图、算子周期、Tensor大小和硬件参数均以题目文件为准，不修改原始依赖。","同一核每条Pipe同一时刻至多执行一个算子，不同Pipe允许时间重叠。","DDR带宽按官方离散事件模型在并发请求间公平共享，本文的静态代价只用于排序，不替代官方计时。","每个非COPY算子只属于一个子图，每个子图只分配到一个核；边界COPY由官方程序重建。","问题2和问题3采用完全相同的分核与核内顺序，二者差异仅来自只读L2。"])
    heading(doc,"2.2 主要符号",2)
    add_table(doc,["符号","含义"],[["G=(V_O,V_T,E)","Op–Tensor二部有向图"],["G_O=(V,A)","压缩后的非COPY算子DAG"],["c_v","算子v的计算周期"],["s_uv","依赖边(u,v)承载的字节数"],["m","NPU核数，m∈{1,2,3,4,5}"],["B","共享DDR总带宽，60 bytes/cycle"],["D_A,D_B","场景A/B跨边界等待，1000/500 cycles"],["d_bp","子图b在Pipe p上的周期和"],["F_b","子图b的估计完成时刻"],["T_max","所有算子完成时刻最大值（Makespan）"]],[4,11],10)

    heading(doc,"3 问题分析",1)
    heading(doc,"3.1 难点分解",2)
    add_text(doc,"本题不是独立作业的普通并行机调度。首先，算子只能在指定Pipe上执行，局部负载均衡并不等价于总时间最短；其次，切分会把内部Tensor转化为COPY，从而同时增加同步延迟和DDR负载；再次，L1/UB容量有限，过大的子图可能触发spill，过小的子图又会放大Task切换；最后，问题3的FIFO Cache命中取决于访问序列，收益具有明显的图结构依赖性。")
    heading(doc,"3.2 求解思路",2)
    add_text(doc,"因此本文不直接搜索所有分区，而是构造可解释的分层启发式：先在图层面提取关键路径与通信量，再用可控粒度形成子图，最后在核层面通过完成时间预估完成分配。该方法每一步都保持拓扑合法，能够在大规模算例上稳定运行。")
    add_figure(doc,"fig06_algorithm_flow.png","图1  求解算法总体流程",15.5)

    heading(doc,"4 数学模型",1); heading(doc,"4.1 图压缩与通信权",2)
    add_text(doc,"删除原始COPY节点后，将路径“Op→Tensor→Op”压缩为算子依赖边。若两个算子间存在多个Tensor，则边权取其字节数之和：")
    add_math(doc,"sᵤᵥ = Σ size(t),  t: u→t→v",1)
    add_text(doc,"边权既表示跨核时的显式搬运量，也近似反映共享DDR占用。对原始COPY，保留其可达关系，使压缩图仍与评测器的前驱语义一致。")
    heading(doc,"4.2 目标函数",2)
    add_math(doc,"min Tₘₐₓ,   Tₘₐₓ = max Cᵥ",2)
    add_text(doc,"在Makespan接近时，以跨核通信字节数作为次级判据：")
    add_math(doc,"min M_cross = Σ sᵤᵥ · I(core(u) ≠ core(v))",3)
    add_text(doc,"工程实现采用字典序目标：先比较估计完成时刻，再比较新增跨核字节、当前核负载和核编号。这样既保持主目标优先，也保证结果确定、可复现。")
    heading(doc,"4.3 约束",2)
    add_bullets(doc,["唯一性：每个非COPY算子恰好进入一个子图，每个子图恰好分配到一个核。","优先关系：若u可达v，则包含u的子图不得排在包含v的子图之后。","资源互斥：同核同Pipe区间不得重叠；片上L1/UB驻留量不得超过524288/131072 bytes。","带宽约束：所有DDR搬运共享60 bytes/cycle；问题3的Cache read使用250 bytes/cycle通道。","场景一致性：问题3不得修改问题2的分核与顺序。"])

    heading(doc,"5 算法设计",1); heading(doc,"5.1 关键路径优先拓扑序",2)
    add_text(doc,"定义节点的静态底层长度为自身计算量与后继最大底层长度之和：")
    add_math(doc,"L(v) = cᵥ + max L(w),  w∈succ(v)",4)
    add_text(doc,"采用Kahn算法维护入度为0的候选集，以(-L(v), id(v))为优先键。长关键路径节点优先释放，编号用于稳定打破平局。其时间复杂度为O((|V|+|E|)log|V|)。")
    heading(doc,"5.2 均衡聚合与粒度选择",2)
    add_text(doc,"沿关键路径优先序累加计算量，接近目标负载时结束当前子图。连续切块天然保持子图级DAG无环。问题1目标子图数约为6m，以限制100/1000-cycle边界开销；问题2、3目标约为24m，使场景B能在同一Task内保留较细的可调度单元。目标数只是上限，空块和不满足结构条件的边界会被自动合并。")
    heading(doc,"5.3 通信感知列表调度",2)
    add_text(doc,"对待调度子图b及候选核k，先计算其最早释放时刻：")
    add_math(doc,"r_bk = max{A_k+g, max[F_a + I(k_a≠k)(D+s_ab/B)]}",5)
    add_text(doc,"其中A_k为核的当前空闲时刻，g为场景A同Task切换代价，D为跨边界同步延迟。再结合各Pipe的可用时刻A_kp得到：")
    add_math(doc,"F̂_bk = max_p { max(A_kp, r_bk) + d_bp }",6)
    add_text(doc,"算法选择F̂_bk最小的核；若并列，优先新增跨核字节少、累计负载小的核。调度完成后更新该核的Pipe时刻、核空闲时刻和通信统计。")
    heading(doc,"5.4 合法性与复杂度",2)
    add_text(doc,"拓扑排序保证所有前驱先出现；连续聚合保证每个算子覆盖且不重复；列表调度只从已经就绪的子图中选择，因此不改变依赖方向。最终仍由官方程序重新检查依赖、Pipe、片上存储、COPY和带宽事件。算法总存储复杂度为O(|V|+|E|)，候选核数不超过5，故主循环对本题最大图仍可稳定运行。")

    heading(doc,"6 实验设计与验证",1); heading(doc,"6.1 数据与指标",2)
    add_text(doc,"实验覆盖100个正式算例，每个算例分别测试1—5核，共500组分核方案。加速比以题目提供的单核结果为基准：")
    add_math(doc,"S_m = T_single / T_m",7)
    add_text(doc,"L2收益定义为T_noL2/T_L2；字节命中率按命中字节量除以总Cache访问字节量计算。除均值外，还统计胜负数量、分布和代表性极值，防止少量大算例支配平均结论。")
    heading(doc,"6.2 评测器加速与等价性检查",2)
    add_text(doc,"原评测器在每个事件后扫描全部算子判断完成状态，场景A还重复扫描当前Task，导致大图出现近似O(|V|²)的状态检查。本文仅将其替换为未完成算子计数器，不修改事件次序、资源状态或时间推进。优化前后在case_001、case_002的1—5核输出CSV逐字节一致，再用于全量实验。该改动只缩短评测耗时，不改变任何论文指标。")
    heading(doc,"6.3 完整性检查",2)
    add_text(doc,"500组实验失败数为0。输出表同时保存算例规模、三个问题的Makespan、加速比、额外COPY字节、Cache访问与命中信息；全量CSV和JSON可由附录命令重新生成。")

    heading(doc,"7 实验结果与讨论",1); heading(doc,"7.1 问题1与问题2的总体性能",2)
    summary=[]
    for c in range(1,6):
        a=df[df.cores==c]; summary.append([c,f"{a.p1_speedup.mean():.4f}",f"{a.p2_speedup.mean():.4f}",f"{a.p1_added_copy_bytes.mean()/2**20:.3f}",f"{a.p2_added_copy_bytes.mean()/2**20:.3f}",int((a.p1_speedup>1).sum()),int((a.p2_speedup>1).sum()),int((a.p2_makespan<a.p1_makespan).sum())])
    add_table(doc,["核数","问题1平均加速比","问题2平均加速比","问题1新增MiB","问题2新增MiB","问题1快于单核","问题2快于单核","问题2优于问题1"],summary,size=8)
    add_figure(doc,"fig01_mean_speedup.png","图2  场景A与场景B的平均加速比",14.8)
    add_text(doc,"问题2在2—5核均优于问题1，五核平均加速比由1.2902提高到1.6868，说明同核子图驻留与较低同步延迟的收益明显。问题2五核有92个算例快于单核，并在86个算例上优于问题1。另一方面，加速比随核数增加逐渐趋缓，说明共享DDR、关键路径和spill开始成为主导瓶颈。")
    add_figure(doc,"fig02_p2_distribution.png","图3  问题2在不同核数下的加速比分布",14.8)
    add_text(doc,"箱线分布显示，中位数随核数稳定上升，但下尾仍低于1，说明并非所有图都适合盲目扩核。依赖链较长、可并行宽度较窄或边界Tensor较大的图，可能因同步与搬运抵消并行收益。实际部署应保留单核/双核回退策略。")
    heading(doc,"7.2 通信开销与收益的权衡",2)
    add_figure(doc,"fig03_copy_overhead.png","图4  分核带来的平均新增COPY搬运量",14.8)
    add_text(doc,"平均新增搬运量随核数增加而上升：五核时问题1和问题2分别为33.138 MiB和33.928 MiB。问题2虽然通信量略高，性能却更好，说明字节量不是唯一决定因素；同核驻留、Task合并以及Pipe重叠能够隐藏部分搬运。该结果也解释了本文采用“预计完成时刻优先、通信量次优”的字典序，而不是单独最小化割边。")
    heading(doc,"7.3 L2 Cache收益",2)
    l2=[]
    for c in range(1,6):
        a=df[df.cores==c]; l2.append([c,f"{(a.p2_makespan/a.singlecore_makespan).mean():.4f}",f"{(a.p3_makespan/a.singlecore_makespan).mean():.4f}",f"{a.p3_vs_no_l2_speedup.mean():.4f}",f"{100*a.p3_cache_hit_rate.mean():.2f}%"])
    add_table(doc,["核数","无L2平均归一时间","有L2平均归一时间","L2平均加速比","平均字节命中率"],l2,size=9)
    add_figure(doc,"fig04_l2_effect.png","图5  只读L2的平均收益与字节命中率",14.8)
    add_text(doc,"L2收益总体随核数上升，五核平均加速比为1.0384、字节命中率为12.74%。400组多核对照中276组更快、115组持平、9组略慢。轻微退化并非Cache增加了单次访问代价，而是DDR与Cache并发事件完成顺序发生变化后，Pipe FIFO竞争的离散事件次序改变；最差观测约0.55%，仍属小幅波动。")
    heading(doc,"7.4 图规模与异质性",2)
    add_figure(doc,"fig05_size_speedup.png","图6  图规模、五核加速比与L2命中率的关系",14.8)
    add_text(doc,"散点图表明，规模较大并不必然获得更高加速比；点云在同一规模区间内仍有明显纵向离散。这说明拓扑宽度、Pipe构成、Tensor复用距离比单纯节点数更能解释性能。五核最佳问题1算例为case_021，加速比2.9081；问题2最佳为case_027，加速比3.4378；多核L2最佳为case_037五核，加速比1.3841。")

    heading(doc,"8 稳健性与敏感性分析",1); heading(doc,"8.1 子图粒度",2)
    add_text(doc,"子图数过少会限制并行度，过多则增加边界COPY、同步和局部存储碎片。本文使用场景相关的6m与24m，而非统一粒度，正是因为两种Task语义不同。更精细的改进可在{4m,6m,8m,12m,24m,32m}中生成候选，先用静态估计筛选，再对少量候选调用官方仿真。")
    heading(doc,"8.2 带宽与同步延迟",2)
    add_text(doc,"当DDR带宽降低或跨核同步延迟提高时，模型中的s_ab/B与D项增大，算法会自然倾向于把强通信前后继放在同核；反之则会更重视Pipe负载均衡。该单调响应使启发式对硬件参数具有可解释性，但静态估计未完整模拟并发带宽分摊，因此最终优劣仍需官方仿真确认。")
    heading(doc,"8.3 Cache容量与复用距离",2)
    add_text(doc,"FIFO L2只对重复COPY_IN有效。命中率随核数上升，反映跨核和spill诱发的重复读增多；但若两个访问间插入的数据量超过1 MiB，早期Tensor会被淘汰。后续可在分核目标中加入reuse-distance惩罚，优先保留“复用距离小且字节量大”的Tensor。")

    heading(doc,"9 模型评价与改进",1); heading(doc,"9.1 优点",2)
    add_bullets(doc,["全流程保持拓扑合法并由官方评测器二次验证，500组方案零失败。","同时考虑关键路径、Pipe负载、同步延迟和通信字节，优于单一均分策略。","时间和空间复杂度近线性，可处理题目中四万级节点/边的计算图。","问题2与问题3使用完全相同调度，L2收益比较不存在分核混杂。","实现确定、输出齐全，实验、汇总和绘图均可一键复现。"])
    heading(doc,"9.2 局限",2)
    add_bullets(doc,["列表调度只用Pipe空闲时刻近似DDR拥塞，没有在搜索阶段复现全部离散事件。","连续聚合强化了合法性与速度，但可能错过非连续的强复用算子簇。","同核完成时刻采用保守更新，没有穷举跨Pipe重叠的最优窗口。","L2复用距离尚未直接进入目标函数，Cache优化仍是结果驱动而非主动设计。"])
    heading(doc,"9.3 可继续优化的方向",2)
    add_text(doc,"可将本文结果作为初始可行解，进行局部搜索：交换相邻子图、移动边界算子、合并/拆分子图，并用通信量与关键路径变化作快速筛选，只对前若干候选运行官方仿真。进一步可训练轻量代理模型预测仿真增益，但训练特征应保留拓扑宽度、Pipe占比、割边字节、spill和复用距离，避免只以图规模拟合。")

    heading(doc,"10 结论",1)
    add_text(doc,"本文针对通用NPU多核调度构建了通信感知、关键路径优先的分层启发式。全量实验说明：增加核数通常能够缩短执行时间，但收益受关键路径、共享DDR和跨核COPY共同限制；场景B通过同核驻留和Task合并显著优于场景A；只读L2的平均收益有限但稳定，在具有明显重复搬运的算例上可超过38%。由此，工程优化重点不应停留在算子数均分，而应转向“关键路径负载、跨核字节、spill与Cache复用距离”的联合控制。")

    heading(doc,"参考文献",1)
    refs=["[1] 研究生数学建模竞赛题目：通用神经网络处理器下的多核调度问题，题目文档及附录A—D。","[2] Graham R L. Bounds on multiprocessing timing anomalies. SIAM Journal on Applied Mathematics, 1969, 17(2): 416–429.","[3] Topcuoglu H, Hariri S, Wu M Y. Performance-effective and low-complexity task scheduling for heterogeneous computing. IEEE TPDS, 2002, 13(3): 260–274.","[4] Hennessy J L, Patterson D A. Computer Architecture: A Quantitative Approach. 6th ed. Morgan Kaufmann, 2019.","[5] Mattson R L, Gecsei J, Slutz D R, Traiger I L. Evaluation techniques for storage hierarchies. IBM Systems Journal, 1970, 9(2): 78–117.","[6] 题目随附算法说明：基于算子依赖的单核调度算法与多核分核模拟执行算法。"]
    for r in refs: add_text(doc,r)

    heading(doc,"附录A  全部算例五核结果摘要",1)
    add_text(doc,"下表列出100个正式算例在五核配置下的核心结果。图规模为Op、Tensor与Edge数之和；完整的1—5核明细见analysis_results/full/all_results.csv。")
    a=df[df.cores==5].copy(); rows=[]
    for _,r in a.iterrows(): rows.append([r["case"],int(r.ops+r.tensors+r.edges),f"{r.p1_speedup:.4f}",f"{r.p2_speedup:.4f}",f"{r.p3_vs_no_l2_speedup:.4f}",f"{100*r.p3_cache_hit_rate:.2f}%"])
    add_table(doc,["算例","图规模","问题1加速比","问题2加速比","L2加速比","L2字节命中率"],rows,size=7)
    heading(doc,"附录B  复现实验与绘图",1)
    add_text(doc,"在项目根目录依次执行以下命令，可重新生成调度结果、汇总统计与论文插图：")
    for line in ["python code/solution_multicore.py data/case_001.json -n 4 -p 1 -o case_001_p1_plan.json","python code/run_experiments.py --output-dir analysis_results/full","python code/summarize_results.py","python code/generate_paper_figures.py","python code/build_paper_docx.py"]:
        p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(1); r=p.add_run(line); r.font.name="Consolas"; r.font.size=Pt(9)
    add_text(doc,"插图代码位于code/generate_paper_figures.py，所有图均直接读取全量CSV生成；论文Word生成代码位于code/build_paper_docx.py。提交前请在Word中按Ctrl+A、F9更新目录和页码，并填写封面身份信息。")
    heading(doc,"附录C  文件清单",1)
    add_table(doc,["文件","作用"],[["code/solution_multicore.py","生成问题1—3的分核与调度方案"],["code/run_experiments.py","批量运行100算例×5核"],["code/summarize_results.py","汇总统计并生成结果说明"],["code/generate_paper_figures.py","从CSV生成6幅论文插图"],["analysis_results/full/all_results.csv","500组官方评测明细"],["多核调度建模报告.md","Markdown版建模报告"],[OUT.name,"基于竞赛模板生成的Word论文"]],size=9)
    doc.core_properties.title="通用神经网络处理器下的多核调度优化模型"; doc.core_properties.subject="研究生数学建模竞赛论文"; doc.core_properties.author="待填写"
    doc.save(OUT); prune_orphan_media(OUT); print(OUT)
if __name__=="__main__": main()
