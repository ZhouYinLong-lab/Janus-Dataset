// Read-only post-import audit. Writes its result outside the Zotero database.
const base = 'D:\\Projects\\Dog\\Janus-Dataset\\zotero-automation';
const libraryID = Zotero.Libraries.userLibraryID;
const outputPath = base + '\\private\\biominer-post-audit.json';
const normalize = value => (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');

function collectionPath(collectionID) {
  const names = [];
  let collection = Zotero.Collections.get(collectionID);
  while (collection) {
    names.unshift(collection.name);
    collection = collection.parentID ? Zotero.Collections.get(collection.parentID) : null;
  }
  return names.join('/');
}

const allItems = await Zotero.Items.getAll(libraryID, false, false);
const matches = allItems.filter(item => item.isRegularItem() && !item.deleted && (
  normalize(item.getField('DOI')) === normalize('10.48550/arXiv.2604.21508') ||
  normalize(item.getField('title')) === normalize('BioMiner: A Multi-modal System for Automated Mining of Protein-Ligand Bioactivity Data from Literature') ||
  (item.getField('url') || '').includes('2604.21508')
));

const results = [];
for (const item of matches) {
  const attachments = await Zotero.Items.getAsync(item.getAttachments());
  const notes = await Zotero.Items.getAsync(item.getNotes());
  results.push({
    key: item.key,
    itemType: Zotero.ItemTypes.getName(item.itemTypeID),
    title: item.getField('title'),
    DOI: item.getField('DOI'),
    url: item.getField('url'),
    collections: item.getCollections().map(collectionPath),
    tags: item.getTags().map(tag => tag.tag).sort(),
    attachments: attachments.map(attachment => ({
      key: attachment.key,
      title: attachment.getField('title'),
      contentType: attachment.attachmentContentType,
      path: attachment.getFilePath()
    })),
    notes: notes.map(note => ({ key: note.key, hasReadingGuide: note.getNote().includes('Janus 阅读导引 12') }))
  });
}

const audit = { time: new Date().toISOString(), matchCount: results.length, results };
await Zotero.File.putContentsAsync(Zotero.File.pathToFile(outputPath), JSON.stringify(audit, null, 2));
return JSON.stringify(audit);
