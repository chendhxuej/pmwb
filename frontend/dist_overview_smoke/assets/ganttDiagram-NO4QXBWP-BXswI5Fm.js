import{g as oe,s as ce,p as le,o as ue,a as de,b as fe,_ as l,c as at,d as kt,aE as he,aF as me,aG as ke,e as ye,K as ge,aH as ve,l as st,aI as pe,aJ as Rt,aK as Nt,aL as Te,aM as xe,aN as be,aO as we,aP as _e,aQ as De,aR as Se,aS as Bt,aT as zt,aU as Ht,aV as jt,aW as qt,aX as Ce,k as Ee,j as Ie,q as Me,z as Ae}from"./mermaid-DKj4AgE6.js";import{K as Fe,L as Le,d as P,X as $e,Y as Oe}from"./element-plus-BYg_X5WA.js";import{d as Ye}from"./isoWeek-DmMij7LS.js";import"./vue-DYPPlUlc.js";var Kt={exports:{}};(function(t,i){(function(n,e){t.exports=e()})(Fe,function(){var n,e,a=1e3,y=6e4,T=36e5,C=864e5,O=31536e6,z=2628e6,F=/^(-|\+)?P(?:([-+]?[0-9,.]*)Y)?(?:([-+]?[0-9,.]*)M)?(?:([-+]?[0-9,.]*)W)?(?:([-+]?[0-9,.]*)D)?(?:T(?:([-+]?[0-9,.]*)H)?(?:([-+]?[0-9,.]*)M)?(?:([-+]?[0-9,.]*)S)?)?$/,q=/\[([^\]]+)]|YYYY|YY|Y|M{1,2}|D{1,2}|H{1,2}|m{1,2}|s{1,2}|SSS/g,$={years:O,months:z,days:C,hours:T,minutes:y,seconds:a,milliseconds:1,weeks:6048e5},R=function(E){return E instanceof Z},N=function(E,p,m){return new Z(E,m,p.$l)},V=function(E){return e.p(E)+"s"},S=function(E){return E<0},H=function(E){return S(E)?Math.ceil(E):Math.floor(E)},tt=function(E){return Math.abs(E)},X=function(E,p){return E?S(E)?{negative:!0,format:""+tt(E)+p}:{negative:!1,format:""+E+p}:{negative:!1,format:""}},Z=function(){function E(m,I,h){var g=this;if(this.$d={},this.$l=h,m===void 0&&(this.$ms=0,this.parseFromMilliseconds()),I)return N(m*$[V(I)],this);if(typeof m=="number")return this.$ms=m,this.parseFromMilliseconds(),this;if(typeof m=="object")return Object.keys(m).forEach(function(r){g.$d[V(r)]=m[r]}),this.calMilliseconds(),this;if(typeof m=="string"){var v=m.match(F);if(v){var k=v.slice(2).map(function(r){return r!=null?Number(r):0});return this.$d.years=k[0],this.$d.months=k[1],this.$d.weeks=k[2],this.$d.days=k[3],this.$d.hours=k[4],this.$d.minutes=k[5],this.$d.seconds=k[6],this.calMilliseconds(),this}}return this}var p=E.prototype;return p.calMilliseconds=function(){var m=this;this.$ms=Object.keys(this.$d).reduce(function(I,h){return I+(m.$d[h]||0)*$[h]},0)},p.parseFromMilliseconds=function(){var m=this.$ms;this.$d.years=H(m/O),m%=O,this.$d.months=H(m/z),m%=z,this.$d.days=H(m/C),m%=C,this.$d.hours=H(m/T),m%=T,this.$d.minutes=H(m/y),m%=y,this.$d.seconds=H(m/a),m%=a,this.$d.milliseconds=m},p.toISOString=function(){var m=X(this.$d.years,"Y"),I=X(this.$d.months,"M"),h=+this.$d.days||0;this.$d.weeks&&(h+=7*this.$d.weeks);var g=X(h,"D"),v=X(this.$d.hours,"H"),k=X(this.$d.minutes,"M"),r=this.$d.seconds||0;this.$d.milliseconds&&(r+=this.$d.milliseconds/1e3,r=Math.round(1e3*r)/1e3);var d=X(r,"S"),f=m.negative||I.negative||g.negative||v.negative||k.negative||d.negative,u=v.format||k.format||d.format?"T":"",_=(f?"-":"")+"P"+m.format+I.format+g.format+u+v.format+k.format+d.format;return _==="P"||_==="-P"?"P0D":_},p.toJSON=function(){return this.toISOString()},p.format=function(m){var I=m||"YYYY-MM-DDTHH:mm:ss",h={Y:this.$d.years,YY:e.s(this.$d.years,2,"0"),YYYY:e.s(this.$d.years,4,"0"),M:this.$d.months,MM:e.s(this.$d.months,2,"0"),D:this.$d.days,DD:e.s(this.$d.days,2,"0"),H:this.$d.hours,HH:e.s(this.$d.hours,2,"0"),m:this.$d.minutes,mm:e.s(this.$d.minutes,2,"0"),s:this.$d.seconds,ss:e.s(this.$d.seconds,2,"0"),SSS:e.s(this.$d.milliseconds,3,"0")};return I.replace(q,function(g,v){return v||String(h[g])})},p.as=function(m){return this.$ms/$[V(m)]},p.get=function(m){var I=this.$ms,h=V(m);return h==="milliseconds"?I%=1e3:I=h==="weeks"?H(I/$[h]):this.$d[h],I||0},p.add=function(m,I,h){var g;return g=I?m*$[V(I)]:R(m)?m.$ms:N(m,this).$ms,N(this.$ms+g*(h?-1:1),this)},p.subtract=function(m,I){return this.add(m,I,!0)},p.locale=function(m){var I=this.clone();return I.$l=m,I},p.clone=function(){return N(this.$ms,this)},p.humanize=function(m){return n().add(this.$ms,"ms").locale(this.$l).fromNow(!m)},p.valueOf=function(){return this.asMilliseconds()},p.milliseconds=function(){return this.get("milliseconds")},p.asMilliseconds=function(){return this.as("milliseconds")},p.seconds=function(){return this.get("seconds")},p.asSeconds=function(){return this.as("seconds")},p.minutes=function(){return this.get("minutes")},p.asMinutes=function(){return this.as("minutes")},p.hours=function(){return this.get("hours")},p.asHours=function(){return this.as("hours")},p.days=function(){return this.get("days")},p.asDays=function(){return this.as("days")},p.weeks=function(){return this.get("weeks")},p.asWeeks=function(){return this.as("weeks")},p.months=function(){return this.get("months")},p.asMonths=function(){return this.as("months")},p.years=function(){return this.get("years")},p.asYears=function(){return this.as("years")},E}(),K=function(E,p,m){return E.add(p.years()*m,"y").add(p.months()*m,"M").add(p.days()*m,"d").add(p.hours()*m,"h").add(p.minutes()*m,"m").add(p.seconds()*m,"s").add(p.milliseconds()*m,"ms")};return function(E,p,m){n=m,e=m().$utils(),m.duration=function(g,v){var k=m.locale();return N(g,{$l:k},v)},m.isDuration=R;var I=p.prototype.add,h=p.prototype.subtract;p.prototype.add=function(g,v){return R(g)?K(this,g,1):I.bind(this)(g,v)},p.prototype.subtract=function(g,v){return R(g)?K(this,g,-1):h.bind(this)(g,v)}}})})(Kt);var Ve=Kt.exports;const We=Le(Ve);var _t=function(){var t=l(function(k,r,d,f){for(d=d||{},f=k.length;f--;d[k[f]]=r);return d},"o"),i=[6,8,10,12,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29,30,31,33,35,36,38,40],n=[1,26],e=[1,27],a=[1,28],y=[1,29],T=[1,30],C=[1,31],O=[1,32],z=[1,33],F=[1,34],q=[1,9],$=[1,10],R=[1,11],N=[1,12],V=[1,13],S=[1,14],H=[1,15],tt=[1,16],X=[1,19],Z=[1,20],K=[1,21],E=[1,22],p=[1,23],m=[1,25],I=[1,35],h={trace:l(function(){},"trace"),yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,weekend:19,weekend_friday:20,weekend_saturday:21,dateFormat:22,inclusiveEndDates:23,topAxis:24,axisFormat:25,tickInterval:26,excludes:27,includes:28,todayMarker:29,title:30,acc_title:31,acc_title_value:32,acc_descr:33,acc_descr_value:34,acc_descr_multiline_value:35,section:36,clickStatement:37,taskTxt:38,taskData:39,click:40,callbackname:41,callbackargs:42,href:43,clickStatementDebug:44,$accept:0,$end:1},terminals_:{2:"error",4:"gantt",6:"EOF",8:"SPACE",10:"NL",12:"weekday_monday",13:"weekday_tuesday",14:"weekday_wednesday",15:"weekday_thursday",16:"weekday_friday",17:"weekday_saturday",18:"weekday_sunday",20:"weekend_friday",21:"weekend_saturday",22:"dateFormat",23:"inclusiveEndDates",24:"topAxis",25:"axisFormat",26:"tickInterval",27:"excludes",28:"includes",29:"todayMarker",30:"title",31:"acc_title",32:"acc_title_value",33:"acc_descr",34:"acc_descr_value",35:"acc_descr_multiline_value",36:"section",38:"taskTxt",39:"taskData",40:"click",41:"callbackname",42:"callbackargs",43:"href"},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[19,1],[19,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[37,2],[37,3],[37,3],[37,4],[37,3],[37,4],[37,2],[44,2],[44,3],[44,3],[44,4],[44,3],[44,4],[44,2]],performAction:l(function(r,d,f,u,_,s,D){var c=s.length-1;switch(_){case 1:return s[c-1];case 2:this.$=[];break;case 3:s[c-1].push(s[c]),this.$=s[c-1];break;case 4:case 5:this.$=s[c];break;case 6:case 7:this.$=[];break;case 8:u.setWeekday("monday");break;case 9:u.setWeekday("tuesday");break;case 10:u.setWeekday("wednesday");break;case 11:u.setWeekday("thursday");break;case 12:u.setWeekday("friday");break;case 13:u.setWeekday("saturday");break;case 14:u.setWeekday("sunday");break;case 15:u.setWeekend("friday");break;case 16:u.setWeekend("saturday");break;case 17:u.setDateFormat(s[c].substr(11)),this.$=s[c].substr(11);break;case 18:u.enableInclusiveEndDates(),this.$=s[c].substr(18);break;case 19:u.TopAxis(),this.$=s[c].substr(8);break;case 20:u.setAxisFormat(s[c].substr(11)),this.$=s[c].substr(11);break;case 21:u.setTickInterval(s[c].substr(13)),this.$=s[c].substr(13);break;case 22:u.setExcludes(s[c].substr(9)),this.$=s[c].substr(9);break;case 23:u.setIncludes(s[c].substr(9)),this.$=s[c].substr(9);break;case 24:u.setTodayMarker(s[c].substr(12)),this.$=s[c].substr(12);break;case 27:u.setDiagramTitle(s[c].substr(6)),this.$=s[c].substr(6);break;case 28:this.$=s[c].trim(),u.setAccTitle(this.$);break;case 29:case 30:this.$=s[c].trim(),u.setAccDescription(this.$);break;case 31:u.addSection(s[c].substr(8)),this.$=s[c].substr(8);break;case 33:u.addTask(s[c-1],s[c]),this.$="task";break;case 34:this.$=s[c-1],u.setClickEvent(s[c-1],s[c],null);break;case 35:this.$=s[c-2],u.setClickEvent(s[c-2],s[c-1],s[c]);break;case 36:this.$=s[c-2],u.setClickEvent(s[c-2],s[c-1],null),u.setLink(s[c-2],s[c]);break;case 37:this.$=s[c-3],u.setClickEvent(s[c-3],s[c-2],s[c-1]),u.setLink(s[c-3],s[c]);break;case 38:this.$=s[c-2],u.setClickEvent(s[c-2],s[c],null),u.setLink(s[c-2],s[c-1]);break;case 39:this.$=s[c-3],u.setClickEvent(s[c-3],s[c-1],s[c]),u.setLink(s[c-3],s[c-2]);break;case 40:this.$=s[c-1],u.setLink(s[c-1],s[c]);break;case 41:case 47:this.$=s[c-1]+" "+s[c];break;case 42:case 43:case 45:this.$=s[c-2]+" "+s[c-1]+" "+s[c];break;case 44:case 46:this.$=s[c-3]+" "+s[c-2]+" "+s[c-1]+" "+s[c];break}},"anonymous"),table:[{3:1,4:[1,2]},{1:[3]},t(i,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:n,13:e,14:a,15:y,16:T,17:C,18:O,19:18,20:z,21:F,22:q,23:$,24:R,25:N,26:V,27:S,28:H,29:tt,30:X,31:Z,33:K,35:E,36:p,37:24,38:m,40:I},t(i,[2,7],{1:[2,1]}),t(i,[2,3]),{9:36,11:17,12:n,13:e,14:a,15:y,16:T,17:C,18:O,19:18,20:z,21:F,22:q,23:$,24:R,25:N,26:V,27:S,28:H,29:tt,30:X,31:Z,33:K,35:E,36:p,37:24,38:m,40:I},t(i,[2,5]),t(i,[2,6]),t(i,[2,17]),t(i,[2,18]),t(i,[2,19]),t(i,[2,20]),t(i,[2,21]),t(i,[2,22]),t(i,[2,23]),t(i,[2,24]),t(i,[2,25]),t(i,[2,26]),t(i,[2,27]),{32:[1,37]},{34:[1,38]},t(i,[2,30]),t(i,[2,31]),t(i,[2,32]),{39:[1,39]},t(i,[2,8]),t(i,[2,9]),t(i,[2,10]),t(i,[2,11]),t(i,[2,12]),t(i,[2,13]),t(i,[2,14]),t(i,[2,15]),t(i,[2,16]),{41:[1,40],43:[1,41]},t(i,[2,4]),t(i,[2,28]),t(i,[2,29]),t(i,[2,33]),t(i,[2,34],{42:[1,42],43:[1,43]}),t(i,[2,40],{41:[1,44]}),t(i,[2,35],{43:[1,45]}),t(i,[2,36]),t(i,[2,38],{42:[1,46]}),t(i,[2,37]),t(i,[2,39])],defaultActions:{},parseError:l(function(r,d){if(d.recoverable)this.trace(r);else{var f=new Error(r);throw f.hash=d,f}},"parseError"),parse:l(function(r){var d=this,f=[0],u=[],_=[null],s=[],D=this.table,c="",W=0,o=0,x=2,b=1,M=s.slice.call(arguments,1),w=Object.create(this.lexer),L={yy:{}};for(var A in this.yy)Object.prototype.hasOwnProperty.call(this.yy,A)&&(L.yy[A]=this.yy[A]);w.setInput(r,L.yy),L.yy.lexer=w,L.yy.parser=this,typeof w.yylloc>"u"&&(w.yylloc={});var dt=w.yylloc;s.push(dt);var Tt=w.options&&w.options.ranges;typeof L.yy.parseError=="function"?this.parseError=L.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function ae(j){f.length=f.length-2*j,_.length=_.length-j,s.length=s.length-j}l(ae,"popStack");function Wt(){var j;return j=u.pop()||w.lex()||b,typeof j!="number"&&(j instanceof Array&&(u=j,j=u.pop()),j=d.symbols_[j]||j),j}l(Wt,"lex");for(var B,et,G,xt,nt={},ht,J,Pt,mt;;){if(et=f[f.length-1],this.defaultActions[et]?G=this.defaultActions[et]:((B===null||typeof B>"u")&&(B=Wt()),G=D[et]&&D[et][B]),typeof G>"u"||!G.length||!G[0]){var bt="";mt=[];for(ht in D[et])this.terminals_[ht]&&ht>x&&mt.push("'"+this.terminals_[ht]+"'");w.showPosition?bt="Parse error on line "+(W+1)+`:
`+w.showPosition()+`
Expecting `+mt.join(", ")+", got '"+(this.terminals_[B]||B)+"'":bt="Parse error on line "+(W+1)+": Unexpected "+(B==b?"end of input":"'"+(this.terminals_[B]||B)+"'"),this.parseError(bt,{text:w.match,token:this.terminals_[B]||B,line:w.yylineno,loc:dt,expected:mt})}if(G[0]instanceof Array&&G.length>1)throw new Error("Parse Error: multiple actions possible at state: "+et+", token: "+B);switch(G[0]){case 1:f.push(B),_.push(w.yytext),s.push(w.yylloc),f.push(G[1]),B=null,o=w.yyleng,c=w.yytext,W=w.yylineno,dt=w.yylloc;break;case 2:if(J=this.productions_[G[1]][1],nt.$=_[_.length-J],nt._$={first_line:s[s.length-(J||1)].first_line,last_line:s[s.length-1].last_line,first_column:s[s.length-(J||1)].first_column,last_column:s[s.length-1].last_column},Tt&&(nt._$.range=[s[s.length-(J||1)].range[0],s[s.length-1].range[1]]),xt=this.performAction.apply(nt,[c,o,W,L.yy,G[1],_,s].concat(M)),typeof xt<"u")return xt;J&&(f=f.slice(0,-1*J*2),_=_.slice(0,-1*J),s=s.slice(0,-1*J)),f.push(this.productions_[G[1]][0]),_.push(nt.$),s.push(nt._$),Pt=D[f[f.length-2]][f[f.length-1]],f.push(Pt);break;case 3:return!0}}return!0},"parse")},g=function(){var k={EOF:1,parseError:l(function(d,f){if(this.yy.parser)this.yy.parser.parseError(d,f);else throw new Error(d)},"parseError"),setInput:l(function(r,d){return this.yy=d||this.yy||{},this._input=r,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:l(function(){var r=this._input[0];this.yytext+=r,this.yyleng++,this.offset++,this.match+=r,this.matched+=r;var d=r.match(/(?:\r\n?|\n).*/g);return d?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),r},"input"),unput:l(function(r){var d=r.length,f=r.split(/(?:\r\n?|\n)/g);this._input=r+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-d),this.offset-=d;var u=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),f.length-1&&(this.yylineno-=f.length-1);var _=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:f?(f.length===u.length?this.yylloc.first_column:0)+u[u.length-f.length].length-f[0].length:this.yylloc.first_column-d},this.options.ranges&&(this.yylloc.range=[_[0],_[0]+this.yyleng-d]),this.yyleng=this.yytext.length,this},"unput"),more:l(function(){return this._more=!0,this},"more"),reject:l(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:l(function(r){this.unput(this.match.slice(r))},"less"),pastInput:l(function(){var r=this.matched.substr(0,this.matched.length-this.match.length);return(r.length>20?"...":"")+r.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:l(function(){var r=this.match;return r.length<20&&(r+=this._input.substr(0,20-r.length)),(r.substr(0,20)+(r.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:l(function(){var r=this.pastInput(),d=new Array(r.length+1).join("-");return r+this.upcomingInput()+`
`+d+"^"},"showPosition"),test_match:l(function(r,d){var f,u,_;if(this.options.backtrack_lexer&&(_={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(_.yylloc.range=this.yylloc.range.slice(0))),u=r[0].match(/(?:\r\n?|\n).*/g),u&&(this.yylineno+=u.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:u?u[u.length-1].length-u[u.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+r[0].length},this.yytext+=r[0],this.match+=r[0],this.matches=r,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(r[0].length),this.matched+=r[0],f=this.performAction.call(this,this.yy,this,d,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),f)return f;if(this._backtrack){for(var s in _)this[s]=_[s];return!1}return!1},"test_match"),next:l(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var r,d,f,u;this._more||(this.yytext="",this.match="");for(var _=this._currentRules(),s=0;s<_.length;s++)if(f=this._input.match(this.rules[_[s]]),f&&(!d||f[0].length>d[0].length)){if(d=f,u=s,this.options.backtrack_lexer){if(r=this.test_match(f,_[s]),r!==!1)return r;if(this._backtrack){d=!1;continue}else return!1}else if(!this.options.flex)break}return d?(r=this.test_match(d,_[u]),r!==!1?r:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:l(function(){var d=this.next();return d||this.lex()},"lex"),begin:l(function(d){this.conditionStack.push(d)},"begin"),popState:l(function(){var d=this.conditionStack.length-1;return d>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),_currentRules:l(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),topState:l(function(d){return d=this.conditionStack.length-1-Math.abs(d||0),d>=0?this.conditionStack[d]:"INITIAL"},"topState"),pushState:l(function(d){this.begin(d)},"pushState"),stateStackSize:l(function(){return this.conditionStack.length},"stateStackSize"),options:{"case-insensitive":!0},performAction:l(function(d,f,u,_){switch(u){case 0:return this.begin("open_directive"),"open_directive";case 1:return this.begin("acc_title"),31;case 2:return this.popState(),"acc_title_value";case 3:return this.begin("acc_descr"),33;case 4:return this.popState(),"acc_descr_value";case 5:this.begin("acc_descr_multiline");break;case 6:this.popState();break;case 7:return"acc_descr_multiline_value";case 8:break;case 9:break;case 10:break;case 11:return 10;case 12:break;case 13:break;case 14:this.begin("href");break;case 15:this.popState();break;case 16:return 43;case 17:this.begin("callbackname");break;case 18:this.popState();break;case 19:this.popState(),this.begin("callbackargs");break;case 20:return 41;case 21:this.popState();break;case 22:return 42;case 23:this.begin("click");break;case 24:this.popState();break;case 25:return 40;case 26:return 4;case 27:return 22;case 28:return 23;case 29:return 24;case 30:return 25;case 31:return 26;case 32:return 28;case 33:return 27;case 34:return 29;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return 20;case 43:return 21;case 44:return"date";case 45:return 30;case 46:return"accDescription";case 47:return 36;case 48:return 38;case 49:return 39;case 50:return":";case 51:return 6;case 52:return"INVALID"}},"anonymous"),rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:weekend\s+friday\b)/i,/^(?:weekend\s+saturday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52],inclusive:!0}}};return k}();h.lexer=g;function v(){this.yy={}}return l(v,"Parser"),v.prototype=h,h.Parser=v,new v}();_t.parser=_t;var Pe=_t;P.extend(Ye);P.extend($e);P.extend(Oe);var Xt={friday:5,saturday:6},U="",Et="",It=void 0,Mt="",ct=[],lt=[],At=new Map,Ft=[],vt=[],ut="",Lt="",Jt=["active","done","crit","milestone","vert"],$t=[],rt="",ft=!1,Ot=!1,Yt="sunday",pt="saturday",Dt=0,Re=l(function(){Ft=[],vt=[],ut="",$t=[],yt=0,Ct=void 0,gt=void 0,Y=[],U="",Et="",Lt="",It=void 0,Mt="",ct=[],lt=[],ft=!1,Ot=!1,Dt=0,At=new Map,rt="",Me(),Yt="sunday",pt="saturday"},"clear"),Ne=l(function(t){rt=t},"setDiagramId"),Be=l(function(t){Et=t},"setAxisFormat"),ze=l(function(){return Et},"getAxisFormat"),He=l(function(t){It=t},"setTickInterval"),je=l(function(){return It},"getTickInterval"),qe=l(function(t){Mt=t},"setTodayMarker"),Xe=l(function(){return Mt},"getTodayMarker"),Ge=l(function(t){U=t},"setDateFormat"),Ue=l(function(){ft=!0},"enableInclusiveEndDates"),Ke=l(function(){return ft},"endDatesAreInclusive"),Je=l(function(){Ot=!0},"enableTopAxis"),Qe=l(function(){return Ot},"topAxisEnabled"),Ze=l(function(t){Lt=t},"setDisplayMode"),ts=l(function(){return Lt},"getDisplayMode"),es=l(function(){return U},"getDateFormat"),Qt=l((t,i)=>{const n=i.toLowerCase().split(/[\s,]+/).filter(e=>e!=="");return[...new Set([...t,...n])]},"mergeTokens"),ss=l(function(t){ct=Qt(ct,t)},"setIncludes"),is=l(function(){return ct},"getIncludes"),ns=l(function(t){lt=Qt(lt,t)},"setExcludes"),rs=l(function(){return lt},"getExcludes"),as=l(function(){return At},"getLinks"),os=l(function(t){ut=t,Ft.push(t)},"addSection"),cs=l(function(){return Ft},"getSections"),ls=l(function(){let t=Gt();const i=10;let n=0;for(;!t&&n<i;)t=Gt(),n++;return vt=Y,vt},"getTasks"),Zt=l(function(t,i,n,e){const a=t.format(i.trim()),y=t.format("YYYY-MM-DD");return e.includes(a)||e.includes(y)?!1:n.includes("weekends")&&(t.isoWeekday()===Xt[pt]||t.isoWeekday()===Xt[pt]+1)||n.includes(t.format("dddd").toLowerCase())?!0:n.includes(a)||n.includes(y)},"isInvalidDate"),us=l(function(t){Yt=t},"setWeekday"),ds=l(function(){return Yt},"getWeekday"),fs=l(function(t){pt=t},"setWeekend"),te=l(function(t,i,n,e){if(!n.length||t.manualEndTime)return;let a;t.startTime instanceof Date?a=P(t.startTime):a=P(t.startTime,i,!0),a=a.add(1,"d");let y;t.endTime instanceof Date?y=P(t.endTime):y=P(t.endTime,i,!0);const[T,C]=hs(a,y,i,n,e);t.endTime=T.toDate(),t.renderEndTime=C},"checkTaskDates"),hs=l(function(t,i,n,e,a){let y=!1,T=null;const C=i.add(1e4,"d");for(;t<=i;){if(y||(T=i.toDate()),y=Zt(t,n,e,a),y&&(i=i.add(1,"d"),i>C))throw new Error("Failed to find a valid date that was not excluded by `excludes` after 10,000 iterations.");t=t.add(1,"d")}return[i,T]},"fixTaskDates"),St=l(function(t,i,n){if(n=n.trim(),l(C=>{const O=C.trim();return O==="x"||O==="X"},"isTimestampFormat")(i)&&/^\d+$/.test(n))return new Date(Number(n));const y=/^after\s+(?<ids>[\d\w- ]+)/.exec(n);if(y!==null){let C=null;for(const z of y.groups.ids.split(" ")){let F=it(z);F!==void 0&&(!C||F.endTime>C.endTime)&&(C=F)}if(C)return C.endTime;const O=new Date;return O.setHours(0,0,0,0),O}let T=P(n,i.trim(),!0);if(T.isValid())return T.toDate();{st.debug("Invalid date:"+n),st.debug("With date format:"+i.trim());const C=new Date(n);if(C===void 0||isNaN(C.getTime())||C.getFullYear()<-1e4||C.getFullYear()>1e4)throw new Error("Invalid date:"+n);return C}},"getStartDate"),ee=l(function(t){const i=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(t.trim());return i!==null?[Number.parseFloat(i[1]),i[2]]:[NaN,"ms"]},"parseDuration"),se=l(function(t,i,n,e=!1){n=n.trim();const y=/^until\s+(?<ids>[\d\w- ]+)/.exec(n);if(y!==null){let F=null;for(const $ of y.groups.ids.split(" ")){let R=it($);R!==void 0&&(!F||R.startTime<F.startTime)&&(F=R)}if(F)return F.startTime;const q=new Date;return q.setHours(0,0,0,0),q}let T=P(n,i.trim(),!0);if(T.isValid())return e&&(T=T.add(1,"d")),T.toDate();let C=P(t);const[O,z]=ee(n);if(!Number.isNaN(O)){const F=C.add(O,z);F.isValid()&&(C=F)}return C.toDate()},"getEndDate"),yt=0,ot=l(function(t){return t===void 0?(yt=yt+1,"task"+yt):t},"parseId"),ms=l(function(t,i){let n;i.substr(0,1)===":"?n=i.substr(1,i.length):n=i;const e=n.split(","),a={};Vt(e,a,Jt);for(let T=0;T<e.length;T++)e[T]=e[T].trim();let y="";switch(e.length){case 1:a.id=ot(),a.startTime=t.endTime,y=e[0];break;case 2:a.id=ot(),a.startTime=St(void 0,U,e[0]),y=e[1];break;case 3:a.id=ot(e[0]),a.startTime=St(void 0,U,e[1]),y=e[2];break}return y&&(a.endTime=se(a.startTime,U,y,ft),a.manualEndTime=P(y,"YYYY-MM-DD",!0).isValid(),te(a,U,lt,ct)),a},"compileData"),ks=l(function(t,i){let n;i.substr(0,1)===":"?n=i.substr(1,i.length):n=i;const e=n.split(","),a={};Vt(e,a,Jt);for(let y=0;y<e.length;y++)e[y]=e[y].trim();switch(e.length){case 1:a.id=ot(),a.startTime={type:"prevTaskEnd",id:t},a.endTime={data:e[0]};break;case 2:a.id=ot(),a.startTime={type:"getStartDate",startData:e[0]},a.endTime={data:e[1]};break;case 3:a.id=ot(e[0]),a.startTime={type:"getStartDate",startData:e[1]},a.endTime={data:e[2]};break}return a},"parseData"),Ct,gt,Y=[],ie={},ys=l(function(t,i){const n={section:ut,type:ut,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:i},task:t,classes:[]},e=ks(gt,i);n.raw.startTime=e.startTime,n.raw.endTime=e.endTime,n.id=e.id,n.prevTaskId=gt,n.active=e.active,n.done=e.done,n.crit=e.crit,n.milestone=e.milestone,n.vert=e.vert,n.vert?n.order=-1:(n.order=Dt,Dt++);const a=Y.push(n);gt=n.id,ie[n.id]=a-1},"addTask"),it=l(function(t){const i=ie[t];return Y[i]},"findTaskById"),gs=l(function(t,i){const n={section:ut,type:ut,description:t,task:t,classes:[]},e=ms(Ct,i);n.startTime=e.startTime,n.endTime=e.endTime,n.id=e.id,n.active=e.active,n.done=e.done,n.crit=e.crit,n.milestone=e.milestone,n.vert=e.vert,Ct=n,vt.push(n)},"addTaskOrg"),Gt=l(function(){const t=l(function(n){const e=Y[n];let a="";switch(Y[n].raw.startTime.type){case"prevTaskEnd":{const y=it(e.prevTaskId);e.startTime=y.endTime;break}case"getStartDate":a=St(void 0,U,Y[n].raw.startTime.startData),a&&(Y[n].startTime=a);break}return Y[n].startTime&&(Y[n].endTime=se(Y[n].startTime,U,Y[n].raw.endTime.data,ft),Y[n].endTime&&(Y[n].processed=!0,Y[n].manualEndTime=P(Y[n].raw.endTime.data,"YYYY-MM-DD",!0).isValid(),te(Y[n],U,lt,ct))),Y[n].processed},"compileTask");let i=!0;for(const[n,e]of Y.entries())t(n),i=i&&e.processed;return i},"compileTasks"),vs=l(function(t,i){let n=i;at().securityLevel!=="loose"&&(n=Ie(i)),t.split(",").forEach(function(e){it(e)!==void 0&&(re(e,()=>{window.open(n,"_self")}),At.set(e,n))}),ne(t,"clickable")},"setLink"),ne=l(function(t,i){t.split(",").forEach(function(n){let e=it(n);e!==void 0&&e.classes.push(i)})},"setClass"),ps=l(function(t,i,n){if(at().securityLevel!=="loose"||i===void 0)return;let e=[];if(typeof n=="string"){e=n.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let y=0;y<e.length;y++){let T=e[y].trim();T.startsWith('"')&&T.endsWith('"')&&(T=T.substr(1,T.length-2)),e[y]=T}}e.length===0&&e.push(t),it(t)!==void 0&&re(t,()=>{Ae.runFunc(i,...e)})},"setClickFun"),re=l(function(t,i){$t.push(function(){const n=rt?`${rt}-${t}`:t,e=document.querySelector(`[id="${n}"]`);e!==null&&e.addEventListener("click",function(){i()})},function(){const n=rt?`${rt}-${t}`:t,e=document.querySelector(`[id="${n}-text"]`);e!==null&&e.addEventListener("click",function(){i()})})},"pushFun"),Ts=l(function(t,i,n){t.split(",").forEach(function(e){ps(e,i,n)}),ne(t,"clickable")},"setClickEvent"),xs=l(function(t){$t.forEach(function(i){i(t)})},"bindFunctions"),bs={getConfig:l(()=>at().gantt,"getConfig"),clear:Re,setDateFormat:Ge,getDateFormat:es,enableInclusiveEndDates:Ue,endDatesAreInclusive:Ke,enableTopAxis:Je,topAxisEnabled:Qe,setAxisFormat:Be,getAxisFormat:ze,setTickInterval:He,getTickInterval:je,setTodayMarker:qe,getTodayMarker:Xe,setAccTitle:fe,getAccTitle:de,setDiagramTitle:ue,getDiagramTitle:le,setDiagramId:Ne,setDisplayMode:Ze,getDisplayMode:ts,setAccDescription:ce,getAccDescription:oe,addSection:os,getSections:cs,getTasks:ls,addTask:ys,findTaskById:it,addTaskOrg:gs,setIncludes:ss,getIncludes:is,setExcludes:ns,getExcludes:rs,setClickEvent:Ts,setLink:vs,getLinks:as,bindFunctions:xs,parseDuration:ee,isInvalidDate:Zt,setWeekday:us,getWeekday:ds,setWeekend:fs};function Vt(t,i,n){let e=!0;for(;e;)e=!1,n.forEach(function(a){const y="^\\s*"+a+"\\s*$",T=new RegExp(y);t[0].match(T)&&(i[a]=!0,t.shift(1),e=!0)})}l(Vt,"getTaskTags");P.extend(We);var ws=l(function(){st.debug("Something is calling, setConf, remove the call")},"setConf"),Ut={monday:Se,tuesday:De,wednesday:_e,thursday:we,friday:be,saturday:xe,sunday:Te},_s=l((t,i)=>{let n=[...t].map(()=>-1/0),e=[...t].sort((y,T)=>y.startTime-T.startTime||y.order-T.order),a=0;for(const y of e)for(let T=0;T<n.length;T++)if(y.startTime>=n[T]){n[T]=y.endTime,y.order=T+i,T>a&&(a=T);break}return a},"getMaxIntersections"),Q,wt=1e4,Ds=l(function(t,i,n,e){const a=at().gantt;e.db.setDiagramId(i);const y=at().securityLevel;let T;y==="sandbox"&&(T=kt("#i"+i));const C=y==="sandbox"?kt(T.nodes()[0].contentDocument.body):kt("body"),O=y==="sandbox"?T.nodes()[0].contentDocument:document,z=O.getElementById(i);Q=z.parentElement.offsetWidth,Q===void 0&&(Q=1200),a.useWidth!==void 0&&(Q=a.useWidth);const F=e.db.getTasks(),q=F.filter(h=>!h.vert);let $=[];for(const h of q)$.push(h.type);$=I($);const R={};let N=2*a.topPadding;if(e.db.getDisplayMode()==="compact"||a.displayMode==="compact"){const h={};for(const v of q)h[v.section]===void 0?h[v.section]=[v]:h[v.section].push(v);let g=0;for(const v of Object.keys(h)){const k=_s(h[v],g)+1;g+=k,N+=k*(a.barHeight+a.barGap),R[v]=k}}else{N+=q.length*(a.barHeight+a.barGap);for(const h of $)R[h]=q.filter(g=>g.type===h).length}z.setAttribute("viewBox","0 0 "+Q+" "+N);const V=C.select(`[id="${i}"]`),S=he().domain([me(F,function(h){return h.startTime}),ke(F,function(h){return h.endTime})]).rangeRound([0,Q-a.leftPadding-a.rightPadding]);function H(h,g){const v=h.startTime,k=g.startTime;let r=0;return v>k?r=1:v<k&&(r=-1),r}l(H,"taskCompare"),F.sort(H),tt(F,Q,N),ye(V,N,Q,a.useMaxWidth),V.append("text").text(e.db.getDiagramTitle()).attr("x",Q/2).attr("y",a.titleTopMargin).attr("class","titleText");function tt(h,g,v){const k=a.barHeight,r=k+a.barGap,d=a.topPadding,f=a.leftPadding,u=ge().domain([0,$.length]).range(["#00B9FA","#F95002"]).interpolate(ve);Z(r,d,f,g,v,h,e.db.getExcludes(),e.db.getIncludes()),E(f,d,g,v),X(h,r,d,f,k,u,g),p(r,d),m(f,d,g,v)}l(tt,"makeGantt");function X(h,g,v,k,r,d,f){h.sort((o,x)=>o.vert===x.vert?0:o.vert?1:-1);const u=h.filter(o=>!o.vert),s=[...new Set(u.map(o=>o.order))].map(o=>u.find(x=>x.order===o));V.append("g").selectAll("rect").data(s).enter().append("rect").attr("x",0).attr("y",function(o,x){return x=o.order,x*g+v-2}).attr("width",function(){return f-a.rightPadding/2}).attr("height",g).attr("class",function(o){for(const[x,b]of $.entries())if(o.type===b)return"section section"+x%a.numberSectionStyles;return"section section0"}).enter();const D=V.append("g").selectAll("rect").data(h).enter(),c=e.db.getLinks();if(D.append("rect").attr("id",function(o){return i+"-"+o.id}).attr("rx",3).attr("ry",3).attr("x",function(o){return o.milestone?S(o.startTime)+k+.5*(S(o.endTime)-S(o.startTime))-.5*r:S(o.startTime)+k}).attr("y",function(o,x){return x=o.order,o.vert?a.gridLineStartPadding:x*g+v}).attr("width",function(o){return o.milestone?r:o.vert?.08*r:S(o.renderEndTime||o.endTime)-S(o.startTime)}).attr("height",function(o){return o.vert?u.length*(a.barHeight+a.barGap)+a.barHeight*2:r}).attr("transform-origin",function(o,x){return x=o.order,(S(o.startTime)+k+.5*(S(o.endTime)-S(o.startTime))).toString()+"px "+(x*g+v+.5*r).toString()+"px"}).attr("class",function(o){const x="task";let b="";o.classes.length>0&&(b=o.classes.join(" "));let M=0;for(const[L,A]of $.entries())o.type===A&&(M=L%a.numberSectionStyles);let w="";return o.active?o.crit?w+=" activeCrit":w=" active":o.done?o.crit?w=" doneCrit":w=" done":o.crit&&(w+=" crit"),w.length===0&&(w=" task"),o.milestone&&(w=" milestone "+w),o.vert&&(w=" vert "+w),w+=M,w+=" "+b,x+w}),D.append("text").attr("id",function(o){return i+"-"+o.id+"-text"}).text(function(o){return o.task}).attr("font-size",a.fontSize).attr("x",function(o){let x=S(o.startTime),b=S(o.renderEndTime||o.endTime);if(o.milestone&&(x+=.5*(S(o.endTime)-S(o.startTime))-.5*r,b=x+r),o.vert)return S(o.startTime)+k;const M=this.getBBox().width;return M>b-x?b+M+1.5*a.leftPadding>f?x+k-5:b+k+5:(b-x)/2+x+k}).attr("y",function(o,x){return o.vert?a.gridLineStartPadding+u.length*(a.barHeight+a.barGap)+60:(x=o.order,x*g+a.barHeight/2+(a.fontSize/2-2)+v)}).attr("text-height",r).attr("class",function(o){const x=S(o.startTime);let b=S(o.endTime);o.milestone&&(b=x+r);const M=this.getBBox().width;let w="";o.classes.length>0&&(w=o.classes.join(" "));let L=0;for(const[dt,Tt]of $.entries())o.type===Tt&&(L=dt%a.numberSectionStyles);let A="";return o.active&&(o.crit?A="activeCritText"+L:A="activeText"+L),o.done?o.crit?A=A+" doneCritText"+L:A=A+" doneText"+L:o.crit&&(A=A+" critText"+L),o.milestone&&(A+=" milestoneText"),o.vert&&(A+=" vertText"),M>b-x?b+M+1.5*a.leftPadding>f?w+" taskTextOutsideLeft taskTextOutside"+L+" "+A:w+" taskTextOutsideRight taskTextOutside"+L+" "+A+" width-"+M:w+" taskText taskText"+L+" "+A+" width-"+M}),at().securityLevel==="sandbox"){let o;o=kt("#i"+i);const x=o.nodes()[0].contentDocument;D.filter(function(b){return c.has(b.id)}).each(function(b){var M=x.querySelector("#"+CSS.escape(i+"-"+b.id)),w=x.querySelector("#"+CSS.escape(i+"-"+b.id+"-text"));const L=M.parentNode;var A=x.createElement("a");A.setAttribute("xlink:href",c.get(b.id)),A.setAttribute("target","_top"),L.appendChild(A),A.appendChild(M),A.appendChild(w)})}}l(X,"drawRects");function Z(h,g,v,k,r,d,f,u){if(f.length===0&&u.length===0)return;let _,s;for(const{startTime:b,endTime:M}of d)(_===void 0||b<_)&&(_=b),(s===void 0||M>s)&&(s=M);if(!_||!s)return;if(P(s).diff(P(_),"year")>5){st.warn("The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.");return}const D=e.db.getDateFormat(),c=[];let W=null,o=P(_);for(;o.valueOf()<=s;)e.db.isInvalidDate(o,D,f,u)?W?W.end=o:W={start:o,end:o}:W&&(c.push(W),W=null),o=o.add(1,"d");V.append("g").selectAll("rect").data(c).enter().append("rect").attr("id",b=>i+"-exclude-"+b.start.format("YYYY-MM-DD")).attr("x",b=>S(b.start.startOf("day"))+v).attr("y",a.gridLineStartPadding).attr("width",b=>S(b.end.endOf("day"))-S(b.start.startOf("day"))).attr("height",r-g-a.gridLineStartPadding).attr("transform-origin",function(b,M){return(S(b.start)+v+.5*(S(b.end)-S(b.start))).toString()+"px "+(M*h+.5*r).toString()+"px"}).attr("class","exclude-range")}l(Z,"drawExcludeDays");function K(h,g,v,k){if(v<=0||h>g)return 1/0;const r=g-h,d=P.duration({[k??"day"]:v}).asMilliseconds();return d<=0?1/0:Math.ceil(r/d)}l(K,"getEstimatedTickCount");function E(h,g,v,k){const r=e.db.getDateFormat(),d=e.db.getAxisFormat();let f;d?f=d:r==="D"?f="%d":f=a.axisFormat??"%Y-%m-%d";let u=pe(S).tickSize(-k+g+a.gridLineStartPadding).tickFormat(Rt(f));const s=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(e.db.getTickInterval()||a.tickInterval);if(s!==null){const D=parseInt(s[1],10);if(isNaN(D)||D<=0)st.warn(`Invalid tick interval value: "${s[1]}". Skipping custom tick interval.`);else{const c=s[2],W=e.db.getWeekday()||a.weekday,o=S.domain(),x=o[0],b=o[1],M=K(x,b,D,c);if(M>wt)st.warn(`The tick interval "${D}${c}" would generate ${M} ticks, which exceeds the maximum allowed (${wt}). This may indicate an invalid date or time range. Skipping custom tick interval.`);else switch(c){case"millisecond":u.ticks(qt.every(D));break;case"second":u.ticks(jt.every(D));break;case"minute":u.ticks(Ht.every(D));break;case"hour":u.ticks(zt.every(D));break;case"day":u.ticks(Bt.every(D));break;case"week":u.ticks(Ut[W].every(D));break;case"month":u.ticks(Nt.every(D));break}}}if(V.append("g").attr("class","grid").attr("transform","translate("+h+", "+(k-50)+")").call(u).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10).attr("dy","1em"),e.db.topAxisEnabled()||a.topAxis){let D=Ce(S).tickSize(-k+g+a.gridLineStartPadding).tickFormat(Rt(f));if(s!==null){const c=parseInt(s[1],10);if(isNaN(c)||c<=0)st.warn(`Invalid tick interval value: "${s[1]}". Skipping custom tick interval.`);else{const W=s[2],o=e.db.getWeekday()||a.weekday,x=S.domain(),b=x[0],M=x[1];if(K(b,M,c,W)<=wt)switch(W){case"millisecond":D.ticks(qt.every(c));break;case"second":D.ticks(jt.every(c));break;case"minute":D.ticks(Ht.every(c));break;case"hour":D.ticks(zt.every(c));break;case"day":D.ticks(Bt.every(c));break;case"week":D.ticks(Ut[o].every(c));break;case"month":D.ticks(Nt.every(c));break}}}V.append("g").attr("class","grid").attr("transform","translate("+h+", "+g+")").call(D).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10)}}l(E,"makeGrid");function p(h,g){let v=0;const k=Object.keys(R).map(r=>[r,R[r]]);V.append("g").selectAll("text").data(k).enter().append(function(r){const d=r[0].split(Ee.lineBreakRegex),f=-(d.length-1)/2,u=O.createElementNS("http://www.w3.org/2000/svg","text");u.setAttribute("dy",f+"em");for(const[_,s]of d.entries()){const D=O.createElementNS("http://www.w3.org/2000/svg","tspan");D.setAttribute("alignment-baseline","central"),D.setAttribute("x","10"),_>0&&D.setAttribute("dy","1em"),D.textContent=s,u.appendChild(D)}return u}).attr("x",10).attr("y",function(r,d){if(d>0)for(let f=0;f<d;f++)return v+=k[d-1][1],r[1]*h/2+v*h+g;else return r[1]*h/2+g}).attr("font-size",a.sectionFontSize).attr("class",function(r){for(const[d,f]of $.entries())if(r[0]===f)return"sectionTitle sectionTitle"+d%a.numberSectionStyles;return"sectionTitle"})}l(p,"vertLabels");function m(h,g,v,k){const r=e.db.getTodayMarker();if(r==="off")return;const d=V.append("g").attr("class","today"),f=new Date,u=d.append("line");u.attr("x1",S(f)+h).attr("x2",S(f)+h).attr("y1",a.titleTopMargin).attr("y2",k-a.titleTopMargin).attr("class","today"),r!==""&&u.attr("style",r.replace(/,/g,";"))}l(m,"drawToday");function I(h){const g={},v=[];for(let k=0,r=h.length;k<r;++k)Object.prototype.hasOwnProperty.call(g,h[k])||(g[h[k]]=!0,v.push(h[k]));return v}l(I,"checkUnique")},"draw"),Ss={setConf:ws,draw:Ds},Cs=l(t=>`
  .mermaid-main-font {
        font-family: ${t.fontFamily};
  }

  .exclude-range {
    fill: ${t.excludeBkgColor};
  }

  .section {
    stroke: none;
    opacity: 0.2;
  }

  .section0 {
    fill: ${t.sectionBkgColor};
  }

  .section2 {
    fill: ${t.sectionBkgColor2};
  }

  .section1,
  .section3 {
    fill: ${t.altSectionBkgColor};
    opacity: 0.2;
  }

  .sectionTitle0 {
    fill: ${t.titleColor};
  }

  .sectionTitle1 {
    fill: ${t.titleColor};
  }

  .sectionTitle2 {
    fill: ${t.titleColor};
  }

  .sectionTitle3 {
    fill: ${t.titleColor};
  }

  .sectionTitle {
    text-anchor: start;
    font-family: ${t.fontFamily};
  }


  /* Grid and axis */

  .grid .tick {
    stroke: ${t.gridColor};
    opacity: 0.8;
    shape-rendering: crispEdges;
  }

  .grid .tick text {
    font-family: ${t.fontFamily};
    fill: ${t.textColor};
  }

  .grid path {
    stroke-width: 0;
  }


  /* Today line */

  .today {
    fill: none;
    stroke: ${t.todayLineColor};
    stroke-width: 2px;
  }


  /* Task styling */

  /* Default task */

  .task {
    stroke-width: 2;
  }

  .taskText {
    text-anchor: middle;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideRight {
    fill: ${t.taskTextDarkColor};
    text-anchor: start;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideLeft {
    fill: ${t.taskTextDarkColor};
    text-anchor: end;
  }


  /* Special case clickable */

  .task.clickable {
    cursor: pointer;
  }

  .taskText.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideLeft.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideRight.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }


  /* Specific task settings for the sections*/

  .taskText0,
  .taskText1,
  .taskText2,
  .taskText3 {
    fill: ${t.taskTextColor};
  }

  .task0,
  .task1,
  .task2,
  .task3 {
    fill: ${t.taskBkgColor};
    stroke: ${t.taskBorderColor};
  }

  .taskTextOutside0,
  .taskTextOutside2
  {
    fill: ${t.taskTextOutsideColor};
  }

  .taskTextOutside1,
  .taskTextOutside3 {
    fill: ${t.taskTextOutsideColor};
  }


  /* Active task */

  .active0,
  .active1,
  .active2,
  .active3 {
    fill: ${t.activeTaskBkgColor};
    stroke: ${t.activeTaskBorderColor};
  }

  .activeText0,
  .activeText1,
  .activeText2,
  .activeText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Completed task */

  .done0,
  .done1,
  .done2,
  .done3 {
    stroke: ${t.doneTaskBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
  }

  .doneText0,
  .doneText1,
  .doneText2,
  .doneText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  /* Done task text displayed outside the bar sits against the diagram background,
     not against the done-task bar, so it must use the outside/contrast color. */
  .doneText0.taskTextOutsideLeft,
  .doneText0.taskTextOutsideRight,
  .doneText1.taskTextOutsideLeft,
  .doneText1.taskTextOutsideRight,
  .doneText2.taskTextOutsideLeft,
  .doneText2.taskTextOutsideRight,
  .doneText3.taskTextOutsideLeft,
  .doneText3.taskTextOutsideRight {
    fill: ${t.taskTextOutsideColor} !important;
  }


  /* Tasks on the critical line */

  .crit0,
  .crit1,
  .crit2,
  .crit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.critBkgColor};
    stroke-width: 2;
  }

  .activeCrit0,
  .activeCrit1,
  .activeCrit2,
  .activeCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.activeTaskBkgColor};
    stroke-width: 2;
  }

  .doneCrit0,
  .doneCrit1,
  .doneCrit2,
  .doneCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
    cursor: pointer;
    shape-rendering: crispEdges;
  }

  .milestone {
    transform: rotate(45deg) scale(0.8,0.8);
  }

  .milestoneText {
    font-style: italic;
  }
  .doneCritText0,
  .doneCritText1,
  .doneCritText2,
  .doneCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  /* Done-crit task text outside the bar — same reasoning as doneText above. */
  .doneCritText0.taskTextOutsideLeft,
  .doneCritText0.taskTextOutsideRight,
  .doneCritText1.taskTextOutsideLeft,
  .doneCritText1.taskTextOutsideRight,
  .doneCritText2.taskTextOutsideLeft,
  .doneCritText2.taskTextOutsideRight,
  .doneCritText3.taskTextOutsideLeft,
  .doneCritText3.taskTextOutsideRight {
    fill: ${t.taskTextOutsideColor} !important;
  }

  .vert {
    stroke: ${t.vertLineColor};
  }

  .vertText {
    font-size: 15px;
    text-anchor: middle;
    fill: ${t.vertLineColor} !important;
  }

  .activeCritText0,
  .activeCritText1,
  .activeCritText2,
  .activeCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .titleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${t.titleColor||t.textColor};
    font-family: ${t.fontFamily};
  }
`,"getStyles"),Es=Cs,Ls={parser:Pe,db:bs,renderer:Ss,styles:Es};export{Ls as diagram};
