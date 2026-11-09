(function(){var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:ee,getOwnPropertySymbols:te,getPrototypeOf:ne}=Object,f=globalThis,p=f.trustedTypes,re=p?p.emptyScript:``,ie=f.reactiveElementPolyfillSupport,m=(e,t)=>e,h={toAttribute(e,t){switch(t){case Boolean:e=e?re:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},g=(e,t)=>!l(e,t),_={attribute:!0,type:String,converter:h,reflect:!1,useDefault:!1,hasChanged:g};Symbol.metadata??=Symbol(`metadata`),f.litPropertyMetadata??=new WeakMap;var v=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=_){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??_}static _$Ei(){if(this.hasOwnProperty(m(`elementProperties`)))return;let e=ne(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(m(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m(`properties`))){let e=this.properties,t=[...ee(e),...te(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?h:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?h:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??g)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};v.elementStyles=[],v.shadowRootOptions={mode:`open`},v[m(`elementProperties`)]=new Map,v[m(`finalized`)]=new Map,ie?.({ReactiveElement:v}),(f.reactiveElementVersions??=[]).push(`2.1.2`);var y=globalThis,b=e=>e,x=y.trustedTypes,ae=x?x.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,oe=`$lit$`,S=`lit$${Math.random().toFixed(9).slice(2)}$`,se=`?`+S,ce=`<${se}>`,C=document,w=()=>C.createComment(``),T=e=>e===null||typeof e!=`object`&&typeof e!=`function`,E=Array.isArray,le=e=>E(e)||typeof e?.[Symbol.iterator]==`function`,D=`[ 	
\f\r]`,O=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,k=/-->/g,A=/>/g,j=RegExp(`>|${D}(?:([^\\s"'>=/]+)(${D}*=${D}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),M=/'/g,N=/"/g,P=/^(?:script|style|textarea|title)$/i,F=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),I=Symbol.for(`lit-noChange`),L=Symbol.for(`lit-nothing`),R=new WeakMap,z=C.createTreeWalker(C,129);function B(e,t){if(!E(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return ae===void 0?t:ae.createHTML(t)}var ue=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=O;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===O?c[1]===`!--`?o=k:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=j):(P.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=j):o=A:o===j?c[0]===`>`?(o=i??O,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?j:c[3]===`"`?N:M):o===N||o===M?o=j:o===k||o===A?o=O:(o=j,i=void 0);let d=o===j&&e[t+1].startsWith(`/>`)?` `:``;a+=o===O?n+ce:l>=0?(r.push(s),n.slice(0,l)+oe+n.slice(l)+S+d):n+S+(l===-2?t:d)}return[B(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},V=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=ue(t,n);if(this.el=e.createElement(l,r),z.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=z.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(oe)){let t=u[o++],n=i.getAttribute(e).split(S),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?fe:r[1]===`?`?pe:r[1]===`@`?me:W}),i.removeAttribute(e)}else e.startsWith(S)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(P.test(i.tagName)){let e=i.textContent.split(S),t=e.length-1;if(t>0){i.textContent=x?x.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],w()),z.nextNode(),c.push({type:2,index:++a});i.append(e[t],w())}}}else if(i.nodeType===8){if(i.data===se)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(S,e+1))!==-1;)c.push({type:7,index:a}),e+=S.length-1}}a++}}static createElement(e,t){let n=C.createElement(`template`);return n.innerHTML=e,n}};function H(e,t,n=e,r){if(t===I)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=T(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=H(e,i._$AS(e,t.values),i,r)),t}var de=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??C).importNode(t,!0);z.currentNode=r;let i=z.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new U(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new he(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=z.nextNode(),a++)}return z.currentNode=C,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},U=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=L,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=H(this,e,t),T(e)?e===L||e==null||e===``?(this._$AH!==L&&this._$AR(),this._$AH=L):e!==this._$AH&&e!==I&&this._(e):e._$litType$===void 0?e.nodeType===void 0?le(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==L&&T(this._$AH)?this._$AA.nextSibling.data=e:this.T(C.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=V.createElement(B(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new de(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=R.get(e.strings);return t===void 0&&R.set(e.strings,t=new V(e)),t}k(t){E(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(w()),this.O(w()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=b(e).nextSibling;b(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},W=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=L,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=L}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=H(this,e,t,0),a=!T(e)||e!==this._$AH&&e!==I,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=H(this,r[n+o],t,o),s===I&&(s=this._$AH[o]),a||=!T(s)||s!==this._$AH[o],s===L?e=L:e!==L&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===L?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},fe=class extends W{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===L?void 0:e}},pe=class extends W{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==L)}},me=class extends W{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=H(this,e,t,0)??L)===I)return;let n=this._$AH,r=e===L&&n!==L||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==L&&(n===L||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},he=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){H(this,e)}},ge=y.litHtmlPolyfillSupport;ge?.(V,U),(y.litHtmlVersions??=[]).push(`3.3.3`);var _e=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new U(t.insertBefore(w(),e),e,void 0,n??{})}return i._$AI(e),i},G=globalThis,K=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=_e(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return I}};K._$litElement$=!0,K.finalized=!0,G.litElementHydrateSupport?.({LitElement:K});var ve=G.litElementPolyfillSupport;ve?.({LitElement:K}),(G.litElementVersions??=[]).push(`4.2.2`);function q(e){return e?.item_id??e?.id}function J(e){return e?.items??[]}function ye(e){return e?.toLowerCase().split(`-`)[0]===`nl`?`nl`:`en`}var be={en:{today:`Today's dinner`,stock:`Stock check`,window:`Menu window`,loading:`Loading…`,empty:`No dinner planned for this day.`,eaten:`Log as eaten`,logged:`Eaten`,swap:`Swap dinner`,apply:`Choose this dinner`,cancel:`Cancel`,noSuggestions:`No valid alternatives are available.`,stockQuestion:`Do you have this item?`,yes:`Yes`,no:`No`,confirmNo:`Confirm no`,replaces:`May replace {count} dinners`,emptyStock:`No stock items to check.`,kcal:`{value} kcal`,balance:{ok:`Balanced`,off_target:`Off target`,unknown:`Balance unknown`},statuses:{planned:`Planned`,pinned:`Pinned`,eaten:`Eaten`,empty:`Empty`},errors:`Could not load Menu Planner.`},nl:{today:`Diner van vandaag`,stock:`Voorraad controleren`,window:`Menuvenster`,loading:`Laden…`,empty:`Er is geen diner gepland voor deze dag.`,eaten:`Markeer als gegeten`,logged:`Gegeten`,swap:`Diner wisselen`,apply:`Kies dit diner`,cancel:`Annuleren`,noSuggestions:`Er zijn geen geldige alternatieven.`,stockQuestion:`Heb je dit ingrediënt?`,yes:`Ja`,no:`Nee`,confirmNo:`Nee bevestigen`,replaces:`Vervangt mogelijk {count} diners`,emptyStock:`Geen voorraaditems om te controleren.`,kcal:`{value} kcal`,balance:{ok:`In balans`,off_target:`Buiten doel`,unknown:`Balans onbekend`},statuses:{planned:`Gepland`,pinned:`Vastgezet`,eaten:`Gegeten`,empty:`Leeg`},errors:`Menu Planner kon niet worden geladen.`}},Y=o`
  :host {
    display: block;
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  }
  ha-card {
    overflow: hidden;
    border-radius: var(--ha-card-border-radius, 12px);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 0;
    font-size: 16px;
    font-weight: 500;
  }
  main { padding: 8px 16px 16px; }
  .muted, .meta { color: var(--secondary-text-color, #727272); }
  .meta { font-size: 12px; }
  .row, .actions, .metrics {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .row { justify-content: space-between; }
  .actions { flex-wrap: wrap; margin-top: 12px; }
  .metrics { flex-wrap: wrap; margin-top: 12px; }
  .chip {
    display: inline-flex;
    align-items: center;
    min-height: 26px;
    padding: 3px 10px;
    border-radius: 14px;
    background: var(--secondary-background-color, #f5f5f5);
    color: var(--secondary-text-color, #727272);
    font-size: 12px;
  }
  .warning { color: var(--error-color, #db4437); }
  button {
    min-height: 36px;
    border: 0;
    border-radius: 18px;
    padding: 0 14px;
    background: transparent;
    color: var(--primary-color, #03a9f4);
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }
  button.primary {
    background: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
  }
  button:disabled { opacity: 0.55; cursor: default; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: 10px 0; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  li:last-child { border-bottom: 0; }
  details { border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  summary { cursor: pointer; list-style: none; padding: 10px 0; }
  summary::-webkit-details-marker { display: none; }
  .components { margin: 0 0 10px 14px; padding-left: 12px; border-left: 2px solid var(--divider-color, #e0e0e0); }
  .components li { padding: 3px 0; border: 0; }
  .error { color: var(--error-color, #db4437); }
`,X=class extends K{static properties={hass:{attribute:!1},config:{attribute:!1},data:{state:!0},loading:{state:!0},error:{state:!0},suggestions:{state:!0},preview:{state:!0}};static styles=Y;constructor(){super(),this.data=null,this.loading=!0,this.error=``,this._refreshTimer=null}setConfig(e){this.config={...e}}get _t(){return be[ye(this.hass?.locale?.language)]}get _title(){return this.config?.title||this._t[this.constructor.titleKey]}connectedCallback(){super.connectedCallback(),this._refreshTimer=window.setInterval(()=>this._load(),6e4)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._refreshTimer)}updated(e){e.has(`hass`)&&this.hass&&!this._loaded&&this._load()}async _ws(e){if(!this.hass)throw Error(`Home Assistant connection is unavailable`);return this.hass.callWS(e)}async _load(){if(this.hass&&!this._loadingRequest){this._loadingRequest=!0,this.loading=!0,this.error=``;try{this.data=await this._fetchData(),this._loaded=!0}catch(e){this.error=e?.message||this._t.errors}finally{this.loading=!1,this._loadingRequest=!1}}}async _fetchData(){return null}async _act(e,t=!0){this.error=``;try{await e(),t&&await this._load()}catch(e){this.error=e?.message||this._t.errors}}_header(e=``){return F`<header><span>${this._title}</span>${e?F`<span class="meta">${e}</span>`:``}</header>`}_error(){return this.error?F`<p class="error" role="alert">${this.error}</p>`:``}static getStubConfig(){return{type:`custom:${this.elementName}`,preview:!0}}static getConfigForm(){return{schema:this.formSchema}}static getConfigElement(){let e=document.createElement(`menu-planner-card-editor`);return e.schema=this.formSchema,e}},Z=class extends X{static titleKey=`today`;static elementName=`menu-planner-today-card`;static formSchema=[{name:`title`,selector:{text:{}}},{name:`show_kcal`,selector:{boolean:{}}},{name:`show_balance`,selector:{boolean:{}}}];static styles=[Y,o`.dinner-title { font-size: 20px; font-weight: 500; }`];async _fetchData(){return this._ws({type:`menu_planner/today`})}async _showSuggestions(){let e=this.data?.date;e&&await this._act(async()=>{this.suggestions=await this._ws({type:`menu_planner/swap/suggestions`,date:e})},!1)}async _applySwap(e){let t=this.data?.date,n=J(e).map(q).filter(Number.isInteger);t&&n.length&&await this._act(async()=>{await this._ws({type:`menu_planner/swap/apply`,date:t,item_ids:n}),this.suggestions=null})}render(){let e=this.data?.dinner,t=J(e),n=this.data?.date,r=this.data?.status===`eaten`,i=Array.isArray(this.suggestions)?this.suggestions:this.suggestions?.suggestions??[];return F`
      <ha-card>
        ${this._header(n||``)}
        <main>
          ${this.loading&&!this.data?F`<p class="muted">${this._t.loading}</p>`:e?F`
                  <div class="dinner-title">${t.map(e=>e.name).join(` · `)}</div>
                  ${this.config?.show_kcal!==!1||this.config?.show_balance!==!1?F`<div class="metrics">
                        ${this.config?.show_kcal===!1?``:F`<span class="chip">${this.data.kcal==null?`—`:this._t.kcal.replace(`{value}`,this.data.kcal)}</span>`}
                        ${this.config?.show_balance===!1?``:F`<span class="chip">${this._t.balance[this.data.balance]||this._t.balance.unknown}</span>`}
                      </div>`:``}
                  ${this.data.warnings?.length?F`<p class="warning">${this.data.warnings.join(`, `)}</p>`:``}
                  <div class="actions">
                    <button class="primary" ?disabled=${r} @click=${()=>this._act(()=>this._ws({type:`menu_planner/eaten`,date:n}))}>
                      ${r?this._t.logged:this._t.eaten}
                    </button>
                    <button ?disabled=${r} @click=${()=>this._showSuggestions()}>${this._t.swap}</button>
                  </div>
                  ${i.length?F`<ul aria-label=${this._t.swap}>
                        ${i.map(e=>F`
                          <li class="row">
                            <span>${J(e).map(e=>e.name).join(` · `)}</span>
                            <button @click=${()=>this._applySwap(e)}>${this._t.apply}</button>
                          </li>
                        `)}
                      </ul>`:this.suggestions?F`<p class="muted">${this._t.noSuggestions}</p>`:``}
                `:F`<p class="muted">${this._t.empty}</p>`}
          ${this._error()}
        </main>
      </ha-card>
    `}getCardSize(){return this.suggestions?5:3}getGridOptions(){return{columns:6,rows:this.getCardSize(),min_columns:3,min_rows:2}}},Q=class extends X{static titleKey=`stock`;static elementName=`menu-planner-stock-card`;static formSchema=[{name:`title`,selector:{text:{}}},{name:`unanswered_only`,selector:{boolean:{}}},{name:`show_impact`,selector:{boolean:{}}},{name:`item_count`,selector:{number:{min:1,max:20,step:1}}}];static styles=[Y,o`.stock-name { font-weight: 500; } .stock-actions { display: flex; gap: 2px; }`];async _fetchData(){let e=await this._ws({type:`menu_planner/stock`,unanswered_first:!0});return(Array.isArray(e)?e:e?.items??[]).filter(e=>!this.config?.unanswered_only||e.in_stock==null).slice(0,Number(this.config?.item_count)||5)}async _answer(e,t){let n=q(e);Number.isInteger(n)&&await this._act(async()=>{await this._ws({type:`menu_planner/stock/set`,item_id:n,in_stock:t}),this.preview=null})}async _previewNo(e){let t=q(e);Number.isInteger(t)&&await this._act(async()=>{this.preview={id:t,result:await this._ws({type:`menu_planner/stock/preview`,item_id:t,in_stock:!1})}},!1)}render(){let e=this.data??[];return F`
      <ha-card>
        ${this._header()}
        <main>
          ${this.loading&&!this.data?F`<p class="muted">${this._t.loading}</p>`:e.length?F`<ul>
                  ${e.map(e=>{let t=q(e),n=this.preview?.id===t?this.preview.result:null;return F`<li>
                      <div class="row">
                        <span class="stock-name">${e.name}</span>
                        <div class="stock-actions">
                          <button aria-label="${this._t.yes}: ${e.name}" @click=${()=>this._answer(e,!0)}>${this._t.yes}</button>
                          <button aria-label="${this._t.no}: ${e.name}" @click=${()=>this.config?.show_impact===!1?this._answer(e,!1):this._previewNo(e)}>${this._t.no}</button>
                        </div>
                      </div>
                      ${n?F`<div class="row">
                            <span class="meta">${this._t.replaces.replace(`{count}`,n.replaces_count)}</span>
                            <button @click=${()=>this._answer(e,!1)}>${this._t.confirmNo}</button>
                          </div>`:e.in_stock==null&&e.replaces_count?F`<div class="meta">${this._t.replaces.replace(`{count}`,e.replaces_count)}</div>`:``}
                    </li>`})}
                </ul>`:F`<p class="muted">${this._t.emptyStock}</p>`}
          ${this._error()}
        </main>
      </ha-card>
    `}getCardSize(){return Math.max(2,Math.min(7,(this.data?.length??3)+1))}getGridOptions(){return{columns:6,rows:this.getCardSize(),min_columns:3,min_rows:2}}},$=class extends X{static titleKey=`window`;static elementName=`menu-planner-window-card`;static formSchema=[{name:`title`,selector:{text:{}}},{name:`day_count`,selector:{number:{min:1,max:60,step:1}}}];async _fetchData(){let e=await this._ws({type:`menu_planner/window`});return(Array.isArray(e)?e:e?.days??[]).slice(0,Number(this.config?.day_count)||14)}render(){let e=this.data??[];return F`
      <ha-card>
        ${this._header(e.length?`${e.length} days`:``)}
        <main>
          ${this.loading&&!this.data?F`<p class="muted">${this._t.loading}</p>`:F`<ul>
                ${e.map(e=>F`
                  <li>
                    <details>
                      <summary>
                        <div class="row">
                          <span>${e.date}</span>
                          <span class="chip">${this._t.statuses[e.status]||e.status}</span>
                        </div>
                        <div class="meta">${J(e.dinner).map(e=>e.name).join(` · `)||this._t.empty}</div>
                      </summary>
                      ${e.dinner?.items?.length?F`<ul class="components">
                            ${e.dinner.items.map(e=>F`<li>${e.name} <span class="meta">· ${e.type}</span></li>`)}
                          </ul>`:``}
                    </details>
                  </li>
                `)}
              </ul>`}
          ${this._error()}
        </main>
      </ha-card>
    `}getCardSize(){return Math.min(12,(this.data?.length??5)+1)}getGridOptions(){return{columns:12,rows:this.getCardSize(),min_columns:4,min_rows:3}}},xe=class extends K{static properties={hass:{attribute:!1},schema:{attribute:!1},data:{state:!0}};static styles=o`:host { display: block; }`;constructor(){super(),this.data={}}setConfig(e){this.data={...e}}_valueChanged(e){this.data=e.detail.value,this.dispatchEvent(new CustomEvent(`config-changed`,{detail:{config:this.data},bubbles:!0,composed:!0}))}render(){return F`<ha-form
      .hass=${this.hass}
      .data=${this.data}
      .schema=${this.schema||[]}
      .computeLabel=${e=>e.name}
      @value-changed=${this._valueChanged}
    ></ha-form>`}};customElements.define(`menu-planner-card-editor`,xe),customElements.define(Z.elementName,Z),customElements.define(Q.elementName,Q),customElements.define($.elementName,$),window.customCards=window.customCards||[],window.customCards.push({type:Z.elementName,name:`Menu Planner: Today`,description:`Today’s planned dinner and swap actions.`,preview:!0},{type:Q.elementName,name:`Menu Planner: Stock`,description:`Confirm whether tracked ingredients are in stock.`,preview:!0},{type:$.elementName,name:`Menu Planner: Window`,description:`Browse the planned menu window.`,preview:!0})})();