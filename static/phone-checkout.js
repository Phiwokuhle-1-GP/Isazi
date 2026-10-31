'use strict';
document.querySelectorAll('[data-pep-choice]').forEach(choice => {
  const form=choice.closest('form');
  function update(){
    const pep=choice.value==='pep';
    form.querySelectorAll('[data-pep-fields]').forEach(el=>{el.hidden=!pep;});
    form.querySelectorAll('[data-gateway-fields]').forEach(el=>{el.hidden=pep;});
    form.querySelectorAll('[data-branch-select]').forEach(el=>{el.required=pep;el.disabled=!pep;});
    const address=form.querySelector('#address');
    if(address) address.closest('label').hidden=choice.value!=='randburg';
    form.querySelectorAll('[data-other-delivery]').forEach(el=>{el.hidden=pep;});
  }
  choice.addEventListener('change',update);update();
});
document.querySelectorAll('[data-branch-search]').forEach(search=>{
  const select=search.closest('.pep-picker').querySelector('select');
  const description=search.closest('.pep-picker').querySelector('[data-branch-description]');
  const showSelection=()=>{description.textContent=select.value ? select.selectedOptions[0].textContent : '';};
  select.addEventListener('change',showSelection);showSelection();
  const options=Array.from(select.options).map(o=>({value:o.value,text:o.textContent}));
  search.addEventListener('input',()=>{
    const value=select.value;const query=search.value.toLowerCase().trim();
    select.replaceChildren();
    options.filter(o=>!o.value || o.value===value || o.text.toLowerCase().includes(query)).forEach(o=>select.add(new Option(o.text,o.value,false,o.value===value)));
  });
});

// Ask for account details only after a checkout payment/delivery choice.
const paymentChoice=document.querySelector('[data-payment-choice]');
if(paymentChoice){
 const accountFields=document.querySelector('[data-checkout-account]');
 const updateAccount=()=>{accountFields.hidden=!paymentChoice.value;accountFields.disabled=!paymentChoice.value;};
 paymentChoice.addEventListener('change',updateAccount);updateAccount();
}
