const updates={
 '10.1038/nbt.3374':'<h1>Janus 阅读导引 05</h1><p>已取得出版社页面导出 PDF，作为本地阅读入口；Nature 正式 PDF 在本机环境要求机构认证。论文报告 367 个 PKIS 化合物、224 个重组激酶和 24 个 GPCR 的筛选，正式数据仍以 DOI 页面和补充表为准。</p><p>先读：kinase profiling 的方法、热图和补充表；挑选一个化合物比较不同激酶。</p><p>读完回答：哪些格子是实际测得的低抑制，哪些是未测试或缺失？</p><p>结论边界：阈值化产生的是我们定义的标签，不能把低数值和缺失格子合并。</p>',
 '10.1021/acs.jcim.0c00155':'<h1>Janus 阅读导引 09</h1><p>已取得作者公开博士论文中对应 LIT-PCBA 的第 3 章，作为明确标注的 author-version chapter；ACS 正式 PDF 在本机环境要求访问权限。</p><p>原论文摘要报告15个靶点、7844个活性和407381个非活性化合物；使用前必须核对版本、去重口径和划分。</p><p>先读：摘要；数据筛选流程；Supporting Information。</p><p>读完回答：负例来自实际实验还是人工构造？作者做了哪些过滤？</p><p>补充阅读：arXiv:2507.21404（2025，预印本）提出泄漏问题，结论尚未在本项目重现。</p>'
};
const lib=Zotero.Libraries.userLibraryID;
const changed=[];
for(const item of await Zotero.Items.getAll(lib,false,false)){
 if(!item.isRegularItem()||item.deleted) continue;
 const doi=(item.getField('DOI')||'').toLowerCase();
 if(!updates[doi]) continue;
 const notes=await Zotero.Items.getAsync(item.getNotes());
 const note=notes.find(n=>n.getNote().includes('Janus 阅读导引'));
 if(note){note.setNote(updates[doi]);await note.saveTx();changed.push(item.key);}
}
return JSON.stringify({updated:changed});
