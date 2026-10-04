import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/skillConfig.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
const {assignTag, descendants, removeBranch} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const moduleUrl = `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`;
const classificationSource = await readFile(new URL('../src/lib/skillClassification.ts', import.meta.url), 'utf8');
const classificationJS = ts.transpileModule(classificationSource, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText.replace(/from ['"]\.\/skillConfig['"]/g, `from '${moduleUrl}'`);
const {classifyTags} = await import(`data:text/javascript;base64,${Buffer.from(classificationJS).toString('base64')}`);
const proposalSource = await readFile(new URL('../src/lib/skillProposals.ts', import.meta.url), 'utf8');
const proposalJS = ts.transpileModule(proposalSource, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020}}).outputText;
const {nodeContext, proposalStatus, pendingProposals, unresolvedProposals, mergeProposals} = await import(`data:text/javascript;base64,${Buffer.from(proposalJS).toString('base64')}`);
const document = {nodes: [{id: 'other', parent_id: null}, {id: 'ds', parent_id: null}, {id: 'stl', parent_id: 'ds'}, {id: 'map', parent_id: 'stl'}, {id: 'dp', parent_id: null}], assignments: {39: 'map', 14: 'dp'}};

test('moving a tag replaces its previous position without mutating the draft', () => {
  const moved = assignTag(document, 39, 'dp');
  assert.equal(moved.assignments[39], 'dp');
  assert.equal(document.assignments[39], 'map');
  assert.equal(assignTag(moved, 39, null).assignments[39], undefined);
});
test('deleting a branch releases only its tags and preserves unrelated roots', () => {
  const removed = removeBranch(document, 'ds');
  assert.deepEqual(removed.nodes.map(node => node.id), ['other', 'dp']);
  assert.deepEqual(removed.assignments, {14: 'dp'});
  assert.deepEqual([...descendants(document, 'ds')].sort(), ['ds', 'map', 'stl']);
});

test('AI progress retains valid proposals on failure and retry skips them', async () => {
  const doc = {nodes: [], assignments: {}};
  const tags = [1, 2, 3].map(id => ({id}));
  let kept = [], calls = 0;
  const events = [];
  const progress = (items, total, waiting) => {kept = items; events.push([items.length, total, waiting]);};
  await assert.rejects(classifyTags(doc, tags, [], async () => {
    if (calls++) throw new Error('timeout');
    return {suggestions: [{tag_id: 1, node_id: 'ds', reason: 'a'}]};
  }, new AbortController().signal, progress), /timeout/);
  assert.deepEqual(events, [[0,3,false], [0,3,true], [1,3,false], [1,3,true]]);
  assert.deepEqual(doc.assignments, {});
  const result = await classifyTags(doc, tags, kept, async working => {
    assert.equal(working.assignments[1], 'ds');
    return {suggestions: [{tag_id:2, node_id:'ds', reason:'b'}, {tag_id:3, node_id:'other', reason:'c'}]};
  }, new AbortController().signal, progress);
  assert.deepEqual(result.map(item => item.tag_id), [1,2,3]);
  assert.deepEqual(doc.assignments, {});
});

test('AI response arriving after stop cannot add suggestions', async () => {
  const controller = new AbortController();
  const items = [];
  const result = await classifyTags({nodes:[], assignments:{}}, [{id:1}], [], async () => {
    controller.abort();
    return {suggestions:[{tag_id:1, node_id:'ds', reason:'a'}]};
  }, controller.signal, suggestions => items.push(suggestions));
  assert.deepEqual(result, []);
  assert.ok(items.every(suggestions => suggestions.length === 0));
});

const proposalNodes = [{id:'other',title:'Khác',description:'Ngoài phạm vi',parent_id:null}, {id:'ds',title:'Cấu trúc dữ liệu',description:'Lưu trữ',parent_id:null}];
const proposalDoc = {nodes:proposalNodes, assignments:{}};
const proposal = {tag_id:38,node_id:'ds',source_node_id:'ds',reason:'Tập hợp',nodes:proposalNodes,status:'pending'};

test('a committed manual assignment disappears from proposals while uncommitted data keeps its row', () => {
  const local = assignTag(proposalDoc,38,'ds');
  assert.equal(proposalStatus(proposal,local),'assigned');
  assert.deepEqual(unresolvedProposals([proposal],local),[]);
  assert.deepEqual(unresolvedProposals([proposal],proposalDoc),[proposal]);
  assert.equal(proposalStatus({...proposal,status:'assigned'},local,local),'assigned');
  assert.equal(proposalStatus(proposal,proposalDoc,proposalDoc),'pending');
  assert.equal(proposalStatus({...proposal,status:'assigned'},proposalDoc,proposalDoc),'pending');
});

test('bulk review excludes rejected, stale and manually assigned tags; approval keeps other pending rows valid', () => {
  const rejected = {...proposal,tag_id:39,status:'rejected'};
  const pending = {...proposal,tag_id:40};
  const stale = {...proposal,tag_id:41,nodes:proposalNodes.map(node=>({...node,description:'old scope'}))};
  const local = assignTag(proposalDoc,38,'other');
  assert.equal(proposalStatus(proposal,local),'assigned');
  assert.equal(proposalStatus(rejected,local,proposalDoc),'rejected');
  assert.deepEqual(pendingProposals([proposal,rejected,pending,stale],local,proposalDoc).map(item=>item.tag_id),[40]);
});

test('manual assignments remove rejected and stale proposals without requiring AI approval', () => {
  const rejected = {...proposal,tag_id:39,status:'rejected'};
  const stale = {...proposal,tag_id:40,nodes:proposalNodes.map(node=>({...node,description:'old scope'}))};
  const local = assignTag(assignTag(proposalDoc,39,'ds'),40,'other');
  assert.deepEqual(unresolvedProposals([proposal,rejected,stale],local),[proposal]);
  assert.deepEqual(unresolvedProposals([{...proposal,status:'assigned'}],proposalDoc),[]);
});

test('changing scope invalidates pending proposals, reordering nodes does not', () => {
  assert.equal(nodeContext(proposalNodes),nodeContext([...proposalNodes].reverse()));
  const changed = {...proposalDoc,nodes:proposalNodes.map(node=>({...node,description:'new scope'}))};
  assert.equal(proposalStatus(proposal,changed,proposalDoc),'stale');
  assert.equal(proposalStatus({...proposal,status:'rejected'},changed,proposalDoc),'rejected');
});

test('retry skips rejected proposals as well as unreviewed results without attaching them', async () => {
  const rejected = {...proposal,status:'rejected'};
  let requested = 0;
  const result = await classifyTags(proposalDoc,[{id:38},{id:39}],[rejected],async working=>{
    requested++;
    assert.equal(working.assignments[38],'ds');
    return {suggestions:[{...proposal,tag_id:39}]};
  },new AbortController().signal,()=>{});
  assert.equal(requested,1);
  assert.equal(result[0].status,'rejected');
  assert.deepEqual(proposalDoc.assignments,{});
});

test('rejected proposals stay hidden after reload and a late AI response cannot resurrect them', () => {
  const rejected = {...proposal, status:'rejected'};
  assert.deepEqual(unresolvedProposals([rejected], proposalDoc), []);
  const merged = mergeProposals([rejected], [proposal, {...proposal, tag_id:39}], proposalDoc);
  assert.deepEqual(unresolvedProposals(merged, proposalDoc).map(item=>item.tag_id), [39]);
});

test('review response keeps batches received during saving and filters committed assignments', () => {
  const latest = [proposal, {...proposal,tag_id:39}];
  const committed = assignTag(proposalDoc,38,'ds');
  assert.deepEqual(mergeProposals(latest, [], committed).map(item=>item.tag_id), [39]);
  assert.deepEqual(mergeProposals([], [proposal], committed), []);
});
