// Recoverable rollback for the BioMiner import. Created items are moved to Zotero Trash.
const base = 'D:\\Projects\\Dog\\Janus-Dataset\\zotero-automation';
const statePath = base + '\\private\\biominer-import-state.json';
if (!(await IOUtils.exists(statePath))) throw new Error('BioMiner import state not found');
const state = JSON.parse(await Zotero.File.getContentsAsync(Zotero.File.pathToFile(statePath)));

for (const membership of state.memberships || []) {
  const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, membership.item);
  const collection = Zotero.Collections.getByLibraryAndKey(Zotero.Libraries.userLibraryID, membership.collection);
  if (item && collection && item.getCollections().includes(collection.id)) {
    item.removeFromCollection(collection.id);
    await item.saveTx();
  }
}

for (const added of state.tags || []) {
  const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, added.item);
  if (item && item.hasTag(added.tag)) {
    item.removeTag(added.tag);
    await item.saveTx();
  }
}

const createdKeys = [...(state.createdAttachments || []), ...(state.createdNotes || []), ...(state.createdItems || [])];
for (const key of createdKeys) {
  const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key);
  if (item && !item.deleted) {
    item.deleted = true;
    await item.saveTx();
  }
}

return JSON.stringify({ run: state.run, movedToTrash: createdKeys });
