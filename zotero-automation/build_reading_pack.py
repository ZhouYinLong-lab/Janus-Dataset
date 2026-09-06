"""Create a beginner reading guide, annotated PDF copies and a reviewed import plan."""
import json, html, re
from pathlib import Path
import requests, fitz
from prepare_intake import ROOT, AUTO, OUT, save

entries=json.loads((AUTO/'inputs/incoming/2026-09-06-janus.json').read_text(encoding='utf-8'))
private=AUTO/'private'; private.mkdir(exist_ok=True)
library=[]
for start in range(0,10000,100):
    batch=requests.get('http://127.0.0.1:23119/api/users/0/items',params={'start':start,'limit':100},timeout=15).json()
    library+=batch
    if len(batch)<100: break
save(private/'library-before.json',library)
extra={
'01':'已核对 PDF 第2页 Table 1：以 pChEMBL=5 为阈值，D2 受体记录中阴性205、阳性6636，阴性约3%；改用阈值6，阴性占比约22%。先看阈值如何改变标签，再看第7页 Tables 9–10 和第11页讨论。比例差异不能单独证明所有遗漏都来自发表偏倚。',
'02':'重点读只有配体信息的模型对照。先用日常语言解释：模型可能通过人为负例的特征认出答案，不一定学会蛋白与分子是否结合。',
'04':'已核对 PDF 第4页 Table 4：化合物25在AAK1的 Ki 为9.1 nM、细胞 NB IC50 为770 nM；在GAK的 Ki 为1700 nM、细胞 NB IC50 >10000 nM。第5页明确将化合物16命名为阴性对照。大于号表示未在报告范围内测得半数效应，不能改写成零活性；空白格也不能改写成阴性。第3页还有AAK1共晶尝试不成功的叙述，属于另一种实验失败，不应与活性阴性混为一类。',
'06':'已核对 PDF 第4页 External validation：WOMBAT 缺少实验确认的阴性，未标注关联被用作推定阴性。第8–9页比较含阴性与active-only模型；第11–12页解释球排除采样。外部来源并不自动等于外部阴性标签可靠。',
'07':'正式论文为2019年，DOI 10.1021/acs.jcim.9b00164；PMC收录时间不能当发表年份。正文网页的Figure 1描述筛文献和抽取测定描述的流程；该方法分类的是assay上下文，未证明能直接抽取阴性结果。',
'08':'已核对 PDF 第6–8页：规则可以投赞成、反对或弃权票，由标签模型处理噪声；第8页保留人工测试集。这里的negative relationship是关系抽取标签，不等于实验阴性。',
'05':'已取得出版社页面导出 PDF，作为本地阅读入口；Nature 正式 PDF 在本机环境要求机构认证。论文报告 367 个 PKIS 化合物、224 个重组激酶和 24 个 GPCR 的筛选，正式数据仍以 DOI 页面和补充表为准。',
'09':'已取得作者公开博士论文中对应 LIT-PCBA 的第 3 章，作为明确标注的 author-version chapter；ACS 正式 PDF 在本机环境要求访问权限。原论文摘要报告15个靶点、7844个活性和407381个非活性化合物；使用前必须核对版本、去重口径和划分。补充阅读：arXiv:2507.21404（2025，预印本）提出泄漏问题，结论尚未在本项目重现。'
}
lines=['# 从偏倚到阴性数据：入门阅读路线','',
'范围：小分子生物活性筛选；具体数据阅读以激酶抑制剂为例。检索与校验：2026-09-06。',
'','第一次建议读 **01 → 04 → 06 → 07 → 09**。02帮助理解另一类偏倚；08用于了解弱监督，其余作为延伸阅读。',
'','这些标注是导读提示。它们标出已检查的段落与表格，不代表已完成所有论文的逐段精读，也不把作者报告的效果视为独立复现。',
'','| 顺序 | 论文 | 要回答的问题 |','|---|---|---|']
payload=[]; duplicates=[]; missing=[]
for e in entries:
    if e.get('review_required'): missing.append(e); continue
    order=e['order']; note=extra.get(order,'')
    paths='；'.join(x['term']+'：PDF第'+','.join(map(str,x['pdf_pages']))+'页' for x in e.get('locators',[]))
    annotation_count=0
    pdf=AUTO/'staging'/f'{order}.pdf'; annotated=AUTO/'staging'/f'{order}-reading.pdf'
    if pdf.exists():
        with fitz.open(pdf) as doc:
            for term in e['terms']:
                count=0
                for page in doc:
                    if count>=2: break
                    for quad in page.search_for(term,quads=True)[:1]:
                        a=page.add_highlight_annot(quad)
                        a.set_colors(stroke=(1,0.85,0.15))
                        a.set_info(title='Janus 阅读提示',content=e['question']+'\n注意：'+e['caution'])
                        a.update(); count+=1; annotation_count+=1
            if order=='04':
                tablepage=doc[3]
                for quad in tablepage.search_for('>10000',quads=True)[:3]:
                    a=tablepage.add_highlight_annot(quad); a.set_info(title='Janus 阅读提示',content='保留 > 符号与 nM 单位；这是测量范围约束，不是零活性。'); a.update(); annotation_count+=1
            if annotated.exists(): annotated.unlink()
            doc.save(annotated)
    card=f"# {order}｜{e['alias']}\n\n{e['title']} ({e['year']})\n\n来源：{e['url']}\n\n## 为什么读\n\n{e['reason']}\n\n## 先读哪里\n\n{e['focus']}\n\n{paths or '未取得可定位PDF：按标题定位出版社正文和摘要；不编造页码。'}\n\n## 已核对的阅读提示\n\n{note or '本轮完成元数据和摘要筛选；细节按上列段落继续核对。'}\n\n## 读完回答\n\n{e['question']}\n\n## 结论边界\n\n{e['caution']}\n"
    cardpath=OUT/'cards'/f'{order}.md'; cardpath.parent.mkdir(exist_ok=True); cardpath.write_text(card,encoding='utf-8')
    lines.append(f"| {order} | [{e['alias']}](cards/{order}.md)（{e['year']}） | {e['question']} |")
    matches=[r for r in library if r.get('data',{}).get('DOI','').lower()==e['DOI'].lower() or re.sub(r'\W','',r.get('data',{}).get('title','')).lower()==re.sub(r'\W','',e['title']).lower()]
    if len(matches)>1: duplicates.append({'order':order,'count':len(matches)}); continue
    data={k:e[k] for k in ['itemType','title','creators','DOI','url','publicationTitle','volume','issue','pages','abstractNote']}
    data['date']=e['year']; data['tags']=[{'tag':'status/unread'},{'tag':'topic/negative-evidence'},{'tag':'topic/bioactivity'}]
    if e.get('core'): data['tags'].append({'tag':'status/core'})
    data['extra']='Janus reading route '+order+'; PMID: '+json.loads((OUT/'metadata'/f'{order}.json').read_text(encoding='utf-8'))['id']
    # Notes are explicitly reading guidance, not fabricated author conclusions.
    notehtml='<h1>Janus 阅读导引 '+order+'</h1>'+''.join('<p>'+html.escape(p)+'</p>' for p in [e['reason'],'先读：'+e['focus'],paths,note,'读后问题：'+e['question'],'边界：'+e['caution'],'来源：'+e['url']] if p)
    payload.append({'order':order,'data':data,'collection_path':e['collection_path'],'existing_key':matches[0]['key'] if matches else None,'note':notehtml,'note_marker':'Janus 阅读导引 '+order,'pdf_path':str(annotated) if annotated.exists() else None,'annotation_count':annotation_count})
lines+=['','## 最小术语表','','- assay：一次测定所采用的实验体系和方法。','- inactive：在某次测定和判定标准下未达到活性要求。','- decoy：按规则构造的对照分子，未必经过实验确认。','- IC50：达到半数抑制效应所需浓度；跨测定体系不可随意比较。','- Ki：抑制常数；与细胞IC50不是同一测量。','- 泛化：模型面对训练时没见过的实验或分子时是否仍然有效。','- 弱监督：用有噪声的规则等信号生成候选标签，再通过模型和人工测试验证。','','## 本次范围与后续方案','','先从04的表4手工整理少量“化合物—靶点—测定—数值—单位—比较符”记录，保留未测试与截断值。再检查这些记录在数据库中是否存在。只有确认能找回新增且可解释的信息，才开展批量抽取与模型比较。当前没有实施数据集扩建或模型训练。','','论文选择按可解释性和直接证据排序；没有量化全领域发表偏倚，也没有将本路线视为穷尽检索。']
(OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
save(private/'import-payload.json',payload)
reports=AUTO/'reports'; reports.mkdir(exist_ok=True)
(reports/'recommended-actions.md').write_text(f'# 本批次导入预览\n\n拟处理{len(payload)}篇，匹配已有{sum(bool(p["existing_key"]) for p in payload)}篇，新增{sum(not p["existing_key"] for p in payload)}篇。\n\n创建独立根收藏集和4个子收藏集；仅添加成员关系、缺失标签和专属导读笔记；挂接带导读高亮的PDF副本。不改原有字段和附件。\n\n正文PDF可用{sum(bool(p["pdf_path"]) for p in payload)}份。\n',encoding='utf-8')
(reports/'duplicate-report.md').write_text('# 重复检查\n\n'+json.dumps(duplicates,ensure_ascii=False)+'\n\n按DOI或规范化标题匹配；多重命中时跳过并审核。\n',encoding='utf-8')
(reports/'missing-metadata.md').write_text('# 缺失字段与附件\n\n'+('\n'.join(f'- {e["order"]}: '+e.get('error','needs review') for e in missing) or '11篇书目信息均已核实。')+'\n\n未取得PDF：'+', '.join(p['order'] for p in payload if not p['pdf_path'])+'；保留稳定链接与导读。\n',encoding='utf-8')
(reports/'library-audit.md').write_text(f'# 导入前审计\n\n现有个人库{len(library)}个对象；仅匹配本清单，不改其他研究收藏集。\n\n已运行既有程序 audit/dry-run（只读）。库备份在本机既有自动化项目的 zotero-backup/2026-09-06-114146；私人快照保存在被git忽略的private目录。\n',encoding='utf-8')
print(json.dumps({'papers':len(payload),'pdfs':sum(bool(p['pdf_path']) for p in payload),'highlights':sum(p['annotation_count'] for p in payload),'duplicates':len(duplicates)}))
