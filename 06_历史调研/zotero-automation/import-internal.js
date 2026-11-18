// Run once in Zotero Tools > Developer > Run JavaScript with
// “作为异步函数执行” enabled. Writes only through Zotero APIs.
 const base='D:\\Projects\\Dog\\Janus-Dataset\\zotero-automation';
 const toFile=p=>Zotero.File.pathToFile(p);
 const payload=JSON.parse(await Zotero.File.getContentsAsync(toFile(base+'\\private\\import-payload.json')));
 const lib=Zotero.Libraries.userLibraryID;
 const statePath=base+'\\private\\import-state.json';
 let state={run:'janus-reading-20260906',backup:'2026-09-06-114146',createdItems:[],createdNotes:[],createdAttachments:[],createdCollections:[],memberships:[],tags:[],failures:[]};
 if(await IOUtils.exists(statePath)) state=JSON.parse(await Zotero.File.getContentsAsync(toFile(statePath)));
 const persist=async(action,key)=>{
  await Zotero.File.putContentsAsync(toFile(statePath),JSON.stringify(state,null,2));
  const logPath=base+'\\logs\\changes.jsonl';
  let previous=await IOUtils.exists(logPath)?await Zotero.File.getContentsAsync(toFile(logPath)):'';
  await Zotero.File.putContentsAsync(toFile(logPath),previous+JSON.stringify({time:new Date().toISOString(),run:state.run,action,key})+'\n');
 };
 const norm=s=>(s||'').toLowerCase().replace(/\W/g,'');
 async function collection(path){
  let parent=false;
  for(const name of path.split('/')){
   const children=parent?Zotero.Collections.getByParent(parent):Zotero.Collections.getByLibrary(lib);
   let c=children.find(x=>x.name===name&&(!parent?!x.parentID:true));
   if(!c){c=new Zotero.Collection(); c.libraryID=lib; c.name=name; if(parent)c.parentID=parent; await c.saveTx(); state.createdCollections.push(c.key);await persist('create_collection',c.key);}
   parent=c.id;
  }
  return parent;
 }
 try{
  await IOUtils.makeDirectory(base+'\\logs',{ignoreExisting:true});
  for(const p of payload){
   try{
    const all=await Zotero.Items.getAll(lib,false,false);
    const matches=all.filter(x=>x.isRegularItem()&&!x.deleted&&(x.getField('DOI').toLowerCase()===p.data.DOI.toLowerCase()||norm(x.getField('title'))===norm(p.data.title)));
    if(matches.length>1)throw new Error('Ambiguous duplicate; skipped');
    let item=matches[0];
    if(!item){item=new Zotero.Item('journalArticle');item.libraryID=lib;item.fromJSON(p.data);await item.saveTx();state.createdItems.push(item.key);await persist('create_item',item.key);}
    const col=await collection(p.collection_path);
    if(!item.getCollections().includes(col)){item.addToCollection(col);await item.saveTx();state.memberships.push({item:item.key,collection:Zotero.Collections.get(col).key});await persist('add_membership',item.key);}
    for(const t of p.data.tags){if(!item.hasTag(t.tag)){item.addTag(t.tag);await item.saveTx();state.tags.push({item:item.key,tag:t.tag});await persist('add_tag',item.key);}}
    const notes=await Zotero.Items.getAsync(item.getNotes());
    if(!notes.some(n=>n.getNote().includes(p.note_marker))){const n=new Zotero.Item('note');n.libraryID=lib;n.parentID=item.id;n.setNote(p.note);await n.saveTx();state.createdNotes.push(n.key);await persist('create_reading_note',n.key);}
    if(p.pdf_path){
     const title='Janus '+p.order+'｜导读高亮副本';
     const attachments=await Zotero.Items.getAsync(item.getAttachments());
     if(!attachments.some(a=>a.getField('title')===title)){
      const a=await Zotero.Attachments.importFromFile({file:toFile(p.pdf_path),parentItemID:item.id,libraryID:lib});
      state.createdAttachments.push(a.key);await persist('import_pdf',a.key);
      a.setField('title',title);await a.saveTx();
     }
    }
   }catch(e){state.failures.push({order:p.order,error:String(e)});await persist('failure',p.order);}
  }
  await persist('complete',null);
 }catch(e){state.failures.push({error:String(e)});await persist('batch_failure',null);}
 return JSON.stringify({items:state.createdItems.length,notes:state.createdNotes.length,pdfs:state.createdAttachments.length,failures:state.failures});
