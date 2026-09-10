// Run inside Zotero's JavaScript runner with "Run as async function" enabled.
// All library writes go through Zotero APIs.
const base = 'D:\\Projects\\Dog\\Janus-Dataset\\zotero-automation';
const toFile = path => Zotero.File.pathToFile(path);
const manifest = JSON.parse(await Zotero.File.getContentsAsync(toFile(base + '\\inputs\\incoming\\2026-09-10-biominer.json')));
const libraryID = Zotero.Libraries.userLibraryID;
const statePath = base + '\\private\\biominer-import-state.json';
const logPath = base + '\\logs\\changes.jsonl';
let state = {
  run: 'janus-biominer-20260910',
  backup: 'zotero-automation/private/backups/2026-09-10-145413/janus-active-data',
  createdItems: [],
  createdNotes: [],
  createdAttachments: [],
  createdCollections: [],
  memberships: [],
  tags: [],
  failures: []
};

if (await IOUtils.exists(statePath)) {
  state = JSON.parse(await Zotero.File.getContentsAsync(toFile(statePath)));
}

const persist = async (action, key, detail = null) => {
  await Zotero.File.putContentsAsync(toFile(statePath), JSON.stringify(state, null, 2));
  const previous = await IOUtils.exists(logPath) ? await Zotero.File.getContentsAsync(toFile(logPath)) : '';
  const entry = { time: new Date().toISOString(), run: state.run, action, key, detail };
  await Zotero.File.putContentsAsync(toFile(logPath), previous + JSON.stringify(entry) + '\n');
};

const normalizeTitle = value => (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
const normalizeDOI = value => (value || '').trim().toLowerCase().replace(/^https?:\/\/(dx\.)?doi\.org\//, '').replace(/^doi:\s*/, '');

async function ensureCollection(path) {
  let parentID = false;
  for (const name of path.split('/')) {
    const candidates = parentID ? Zotero.Collections.getByParent(parentID) : Zotero.Collections.getByLibrary(libraryID);
    let collection = candidates.find(candidate => candidate.name === name && (parentID || !candidate.parentID));
    if (!collection) {
      collection = new Zotero.Collection();
      collection.libraryID = libraryID;
      collection.name = name;
      if (parentID) collection.parentID = parentID;
      await collection.saveTx();
      state.createdCollections.push(collection.key);
      await persist('create_collection', collection.key, name);
    }
    parentID = collection.id;
  }
  return parentID;
}

for (const record of manifest) {
  try {
    const data = record.data;
    const allItems = await Zotero.Items.getAll(libraryID, false, false);
    const matches = allItems.filter(item => {
      if (!item.isRegularItem() || item.deleted) return false;
      const sameDOI = normalizeDOI(item.getField('DOI')) === normalizeDOI(data.DOI);
      const sameTitle = normalizeTitle(item.getField('title')) === normalizeTitle(data.title);
      const sameURL = (item.getField('url') || '').includes('2604.21508');
      return sameDOI || sameTitle || sameURL;
    });

    if (matches.length > 1) throw new Error('Ambiguous duplicate: more than one matching parent item');

    let item = matches[0];
    if (!item) {
      item = new Zotero.Item(data.itemType || 'preprint');
      item.libraryID = libraryID;
      item.fromJSON(data);
      await item.saveTx();
      state.createdItems.push(item.key);
      await persist('create_item', item.key, data.title);
    }

    const collectionID = await ensureCollection(record.collection_path);
    if (!item.getCollections().includes(collectionID)) {
      item.addToCollection(collectionID);
      await item.saveTx();
      const collection = Zotero.Collections.get(collectionID);
      state.memberships.push({ item: item.key, collection: collection.key });
      await persist('add_membership', item.key, collection.name);
    }

    for (const tag of data.tags || []) {
      if (!item.hasTag(tag.tag)) {
        item.addTag(tag.tag);
        await item.saveTx();
        state.tags.push({ item: item.key, tag: tag.tag });
        await persist('add_tag', item.key, tag.tag);
      }
    }

    const notes = await Zotero.Items.getAsync(item.getNotes());
    if (!notes.some(note => note.getNote().includes(record.note_marker))) {
      const note = new Zotero.Item('note');
      note.libraryID = libraryID;
      note.parentID = item.id;
      note.setNote(record.note);
      await note.saveTx();
      state.createdNotes.push(note.key);
      await persist('create_reading_note', note.key, record.note_marker);
    }

    const attachmentTitle = 'Janus 12｜BioMiner arXiv PDF';
    const attachments = await Zotero.Items.getAsync(item.getAttachments());
    if (!attachments.some(attachment => attachment.getField('title') === attachmentTitle)) {
      const attachment = await Zotero.Attachments.importFromFile({
        file: toFile(record.pdf_path),
        parentItemID: item.id,
        libraryID
      });
      attachment.setField('title', attachmentTitle);
      await attachment.saveTx();
      state.createdAttachments.push(attachment.key);
      await persist('import_pdf', attachment.key, attachmentTitle);
    }

    await persist('complete_item', item.key, data.title);
  } catch (error) {
    state.failures.push({ order: record.order, error: String(error) });
    await persist('failure', record.order, String(error));
  }
}

await persist('complete', null, { failures: state.failures.length });
return JSON.stringify(state);
