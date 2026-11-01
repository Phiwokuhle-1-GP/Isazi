'use strict';
document.querySelectorAll('[data-pep-choice]').forEach(choice => {
  const form=choice.closest('form');
  function update(){
    const pep=choice.value==='pep';
    form.querySelectorAll('[data-pep-fields]').forEach(el=>{el.hidden=!pep;});
    form.querySelectorAll('[data-gateway-fields]').forEach(el=>{el.hidden=pep;});
    form.querySelectorAll('[data-branch-select]').forEach(el=>{el.required=pep;el.disabled=!pep;});
    const address=form.querySelector('#address');
    if(address) address.closest('label').hidden=!['courier','randburg'].includes(choice.value);
    form.querySelectorAll('[data-other-delivery]').forEach(el=>{el.hidden=pep;});
  }
  choice.addEventListener('change',update);update();
});
document.querySelectorAll('[data-branch-search]').forEach(search=>{
  const picker=search.closest('.pep-picker');
  const select=picker.querySelector('[data-branch-select]');
  const description=picker.querySelector('[data-branch-description]');
  const list=picker.querySelector('.pep-suggestions');
  const status=picker.querySelector('[data-branch-search-status]');
  const normalize=text=>text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const options=Array.from(select.options).map(o=>({value:o.value,text:o.textContent,key:normalize(o.textContent)}));
  let active=-1, matches=[];
  function close(){list.hidden=true;search.setAttribute('aria-expanded','false');search.removeAttribute('aria-activedescendant');active=-1;}
  function showSelection(){description.textContent=select.value ? select.selectedOptions[0].textContent : '';}
  function choose(item){
    select.replaceChildren(new Option(options[0].text,''),new Option(item.text,item.value,true,true));
    search.value=item.text;close();select.dispatchEvent(new Event('change',{bubbles:true}));
    status.textContent='Selected: '+item.text;
  }
  select.addEventListener('change',()=>{showSelection();close();});showSelection();
  search.addEventListener('input',()=>{
    const query=normalize(search.value);
    close();list.replaceChildren();
    // A changed search clears an earlier branch so the wrong store cannot be submitted.
    select.value='';showSelection();
    if(query.length<3){
      select.replaceChildren(...options.map(o=>new Option(o.text,o.value)));
      status.textContent='Type 3 or more characters to see matching PEP stores.';return;
    }
    const terms=query.split(' ');
    matches=options.filter(o=>o.value && terms.every(t=>o.key.includes(t)));
    matches.sort((a,b)=>Number(b.key.startsWith(query))-Number(a.key.startsWith(query)) || a.text.localeCompare(b.text));
    select.replaceChildren(new Option(options[0].text,''),...matches.map(o=>new Option(o.text,o.value)));
    matches.slice(0,8).forEach((item,index)=>{
      const li=document.createElement('li');li.id='pep-suggestion-'+index;li.setAttribute('role','option');li.setAttribute('aria-selected','false');
      const button=document.createElement('button');button.type='button';button.textContent=item.text;button.tabIndex=-1;
      button.addEventListener('click',()=>choose(item));li.append(button);list.append(li);
    });
    status.textContent=matches.length ? matches.length+' matching stores. Choose a suggestion or use the branch list.' : 'No matching stores. Try another town, suburb or branch code.';
    list.hidden=!matches.length;search.setAttribute('aria-expanded',String(matches.length>0));
  });
  search.addEventListener('keydown',event=>{
    if(event.key==='Escape'){close();return;}
    const rows=Array.from(list.children);
    if(list.hidden || !rows.length)return;
    if(event.key==='ArrowDown' || event.key==='ArrowUp'){
      event.preventDefault();active=active<0 ? (event.key==='ArrowDown'?0:rows.length-1) : (active+(event.key==='ArrowDown'?1:-1)+rows.length)%rows.length;
      rows.forEach((row,index)=>row.setAttribute('aria-selected',String(index===active)));
      search.setAttribute('aria-activedescendant',rows[active].id);rows[active].scrollIntoView({block:'nearest'});
    }else if(event.key==='Enter' && active>=0){event.preventDefault();choose(matches[active]);}
  });
  picker.addEventListener('focusout',event=>{if(!picker.contains(event.relatedTarget))close();});
});

// Ask for account details only after a checkout payment/delivery choice.
const paymentChoice=document.querySelector('[data-payment-choice]');
if(paymentChoice && document.querySelector('[data-checkout-account]')){
 const accountFields=document.querySelector('[data-checkout-account]');
 const updateAccount=()=>{accountFields.hidden=!paymentChoice.value;accountFields.disabled=!paymentChoice.value;};
 paymentChoice.addEventListener('change',updateAccount);updateAccount();
}
