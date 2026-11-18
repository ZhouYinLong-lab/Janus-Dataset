// Optional non-destructive rollback in Zotero: detach only this run's memberships/tags.
// Created papers, notes, PDFs and collections remain in the library for recovery.
(async()=>{
 const path='D:/Projects/Dog/Janus-Dataset/zotero-automation/private/import-state.json';
 const s=JSON.parse(await Zotero.File.getContentsAsync(path)); const lib=Zotero.Libraries.userLibraryID;
 for(const x of s.memberships){const i=Zotero.Items.getByLibraryAndKey(lib,x.item),c=Zotero.Collections.getByLibraryAndKey(lib,x.collection);if(i&&c&&i.getCollections().includes(c.id)){i.removeFromCollection(c.id);await i.saveTx();}}
 for(const x of s.tags){const i=Zotero.Items.getByLibraryAndKey(lib,x.item);if(i&&i.hasTag(x.tag)){i.removeTag(x.tag);await i.saveTx();}}
 return 'Removed added memberships and tags; retained all papers, notes, attachments and collections.';
})()
