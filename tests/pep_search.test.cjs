// Development-only DOM tests using the real PAXI directory, without network calls.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require(process.env.CART_TEST_DOM || 'linkedom');
const source=fs.readFileSync(path.join(__dirname,'../static/phone-checkout.js'),'utf8');
const directory=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/paxi_branches.json'),'utf8')).branches;
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function setup(){
 const {window,document}=parseHTML(`<html><body><form><div class="pep-picker"><input data-branch-search aria-expanded="false"><ul class="pep-suggestions" hidden></ul><p data-branch-search-status></p><select data-branch-select><option value="">Select a branch</option>${directory.map(b=>`<option value="${escape(b.code)}">${escape(b.name)} (${escape(b.code)}) · ${escape(b.town)} · ${escape(b.province)}</option>`).join('')}</select><p data-branch-description></p></div></form></body></html>`);
 Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value || '';},set(value){this.querySelectorAll('option').forEach(o=>{if(o.value===value)o.setAttribute('selected','');else o.removeAttribute('selected');});}});
 Object.defineProperty(window.HTMLSelectElement.prototype,'selectedOptions',{configurable:true,get(){return Array.from(this.querySelectorAll('option[selected]'));}});
 window.HTMLElement.prototype.scrollIntoView=function(){};
 function Option(text,value,defaultSelected,selected){const o=document.createElement('option');o.textContent=text;o.value=value;if(selected)o.setAttribute('selected','');return o;}
 vm.runInNewContext(source,{document,Option,Event:window.Event});
 const search=document.querySelector('[data-branch-search]'),select=document.querySelector('select'),list=document.querySelector('ul');
 return {document,search,select,list,type(value){search.value=value;search.dispatchEvent(new window.Event('input',{bubbles:true}));},key(key){const e=new window.Event('keydown',{bubbles:true,cancelable:true});e.key=key;search.dispatchEvent(e);},click(){list.querySelector('button').dispatchEvent(new window.Event('click',{bubbles:true}));}};
}
test('two characters do not suggest; three characters suggest without selecting',()=>{
 const h=setup();h.type('ra');assert.ok(h.list.hidden);h.type('ran');assert.equal(h.list.hidden,false);assert.ok(h.list.children.length>0 && h.list.children.length<=8);assert.equal(h.select.value,'');assert.equal(h.search.getAttribute('aria-expanded'),'true');h.click();assert.ok(h.select.value);assert.ok(directory.some(b=>b.code===h.select.value));assert.equal(h.list.hidden,true);
});
test('keyboard selection, accent insensitive search and changed-query clearing',()=>{
 const h=setup();h.type('JÓH');assert.equal(h.list.hidden,false);h.key('ArrowDown');h.key('Enter');assert.ok(h.select.value);h.type('not-a-real-town-xyz');assert.equal(h.select.value,'');assert.ok(h.list.hidden);assert.match(h.document.querySelector('[data-branch-search-status]').textContent,/No matching stores/);
});
test('branch-code search only returns actual directory entries',()=>{
 const h=setup();const code=directory[0].code;h.type(code);assert.equal(h.list.hidden,false);h.key('ArrowUp');h.key('Enter');assert.ok(directory.some(b=>b.code===h.select.value));
});
