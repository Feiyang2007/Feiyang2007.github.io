import fs from 'fs';
const KEY = process.env.SILICONFLOW_CN_API_KEY;
const URL_ = "https://api.siliconflow.cn/v1/embeddings";
const MODEL = "BAAI/bge-m3";
if(!KEY){console.error("NO KEY");process.exit(1);}

// 1. 从页面源码提取 DOCS
const html = fs.readFileSync('projects/knowledge-rag.html','utf8');
const docsM = html.match(/const DOCS = \[[\s\S]*?\n\];/);
const tmp = docsM[0] + ";globalThis.__D=DOCS;";
eval(tmp);
const DOCS = globalThis.__D;
const texts = DOCS.map(d => "【"+d[0]+"·"+d[1]+"】"+d[2]);

// 2. 批量向量化
async function embed(batch){
  const r = await fetch(URL_,{method:"POST",headers:{"Authorization":"Bearer "+KEY,"Content-Type":"application/json"},body:JSON.stringify({model:MODEL,input:batch})});
  if(!r.ok) throw new Error("HTTP "+r.status+" "+await r.text());
  const j = await r.json();
  return j.data.map(x=>x.embedding);
}
const vecs=[];
for(let i=0;i<texts.length;i+=12){ vecs.push(...await embed(texts.slice(i,i+12))); }
console.log("dim:",vecs[0].length,"docs:",vecs.length);

// 3. 写 rag-vectors.js（含模型与维度元数据）
fs.writeFileSync('projects/rag-vectors.js',
  "// 自动生成：语料文档向量（bge-m3）。请勿手改；语料变更后重跑 build。\n"+
  "window.RAG_VECS = "+JSON.stringify({model:MODEL,dim:vecs[0].length,version:"v1-"+DOCS.length,vectors:vecs})+";\n");

// 4. 余弦检索质量自检
function cosine(a,b){let d=0,na=0,nb=0;for(let i=0;i<a.length;i++){d+=a[i]*b[i];na+=a[i]*a[i];nb+=b[i]*b[i];}return d/(Math.sqrt(na)*Math.sqrt(nb)||1);}
const qs=["你是怎么选方向的？","为什么从土木转大数据？","RAG 解决什么问题","KNN 的 K 值怎么选","qpos 和 qvel 是什么","你做过哪些项目","现在最优先的事"];
const qv = await embed(qs);
qv.forEach((v,i)=>{
  const rank = DOCS.map((d,j)=>({t:d[1],s:cosine(v,vecs[j])})).sort((a,b)=>b.s-a.s).slice(0,3);
  console.log("\nQ:",qs[i]); console.log("  →", rank.map(r=>r.t+"("+r.s.toFixed(3)+")").join(" | "));
});
console.log("\nWROTE projects/rag-vectors.js");
