'use strict';
document.addEventListener('DOMContentLoaded',()=>{
 document.querySelectorAll('[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{
   if(!window.confirm(form.dataset.confirm||'Are you sure?'))event.preventDefault();
 }));
 document.querySelectorAll('[data-print]').forEach(btn=>btn.addEventListener('click',()=>window.print()));
 const search=document.querySelector('#story-filter');
 if(search){search.addEventListener('input',()=>{const q=search.value.trim().toLowerCase();document.querySelectorAll('[data-story]').forEach(row=>{row.hidden=!row.dataset.story.includes(q);});});}
 const toggle=document.querySelector('[data-kanban]');
 if(toggle){toggle.addEventListener('click',()=>{const board=document.querySelector('#kanban');const table=document.querySelector('#story-table');board.hidden=!board.hidden;table.hidden=!table.hidden;toggle.textContent=board.hidden?'Toggle board':'Toggle table';});}
});
document.addEventListener('DOMContentLoaded',()=>{
 const container=document.querySelector('#design-preview-frame');
 document.querySelectorAll('[data-device]').forEach(btn=>btn.addEventListener('click',()=>{
  if(!container)return;
  const mobile=btn.dataset.device==='mobile';
  container.classList.toggle('mobile',mobile);
  document.querySelectorAll('[data-device]').forEach(item=>item.classList.toggle('active',item===btn));
 }));
});
