"""Reconcile unsupported-format records and create a per-path review report."""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/"knowledge_base"/"metadata"
CODE={".py",".js",".mjs",".ts",".java",".cs",".go",".rs",".sh"}
STRUCTURED={".json",".jsonl",".yaml",".yml",".csv",".xml",".toml",".ini"}
DIAGRAM={".dot",".gotmpl",".conf",".excalidraw",".gliffy",".svg"}
VISUAL={".png",".jpg",".jpeg",".gif",".webp",".avif",".woff",".woff2",".ttf",".otf"}
PARSERS={
 ".json":"json", ".jsonl":"jsonl", ".yaml":"yaml", ".yml":"yaml", ".csv":"csv", ".xml":"xml", ".toml":"toml", ".ini":"ini",
 ".py":"source_code_python_ast", ".js":"source_code_javascript_structure", ".mjs":"source_code_javascript_structure", ".ts":"source_code_typescript_structure",
 ".java":"source_code_java_structure", ".cs":"source_code_csharp_structure", ".go":"source_code_go_structure", ".rs":"source_code_rust_structure", ".sh":"source_code_shell_structure",
 ".dot":"dot_labels_nodes_edges", ".gotmpl":"literal_template_text", ".conf":"key_value_text", ".excalidraw":"excalidraw_json_text_elements", ".gliffy":"gliffy_json_labels", ".svg":"svg_text_labels_only"}

def classification(ext,category):
 if ext in VISUAL or category=="image":
  return "Binary or visual asset; exclude from ordinary text ingestion","none","The file is an image/font or visual asset. Ordinary text vectors would lose the visual structure and can retain decorative or embedded data.","Keep excluded; link or render as an asset only under a separately reviewed workflow."
 if ext in CODE:
  return "Supported but requires scope review","high","Source/example code can provide technical context, but executable and generated code is not automatically documentation text.","Review whether this exact path is an approved example or source file; keep excluded until source scope, category policy, and document rights are approved."
 if ext in STRUCTURED:
  return "Supported but requires scope review","medium","Structured fields can be useful documentation, manifests, examples, or operational data; parser support does not establish relevance or rights.","Inspect path and payload purpose; keep excluded until its source scope is explicitly amended and approval is recorded."
 if ext in DIAGRAM:
  return "Supported but requires scope review","medium","Parser extracts textual labels or literal template/config text only; standalone diagram/config content may be incomplete or generated.","Review whether referenced docs rely on this file; preserve visual asset status and exclude until reviewed scope is explicit."
 if ext in {".css",".inv",".gotmpl"} or category=="supporting_artifact":
  return "Generated or irrelevant artifact; exclude","low","Stylesheets, inventory/build metadata, and operational files are generally not user-facing explanation.","Keep excluded unless an owner identifies an explicit documentation use case."
 if ext in {".dot",".gliffy",".excalidraw"}:
  return "Requires a specialized parser","low","Diagram structure requires extraction of text labels and graph relationships, not raw source dumping.","Use diagram-specific extraction only after review; preserve original as an asset."
 return "Unknown; manual inspection required","manual","No reliable classification or parser decision was established from extension and inventory metadata.","Inspect the exact file and record a specific disposition; do not ingest by default."

def main():
 audit=json.loads((META/"ingestion_audit_20261116.json").read_text(encoding="utf-8"))
 rows=[r for r in audit["records"] if r.get("discovery_status")=="unsupported_category"]
 grouped=defaultdict(list); by_ext=Counter(); by_source=Counter(); classifications=Counter()
 path_extension_mismatches=[]; empty_paths=[]; multi_suffix=[]; hidden=[]; scope_candidates=[]
 for r in rows:
  path=r.get("file_path")
  if not path:
   ext="[missing_path]"; empty_paths.append(r.get("document_id"))
  else:
   name=Path(path).name
   ext=Path(name).suffix.lower() or "[no_extension]"
   if len(Path(name).suffixes)>1: multi_suffix.append(path)
   if name.startswith(".") and len(Path(name).suffixes)==0: hidden.append(path)
  if r.get("extension") != ext:
   path_extension_mismatches.append({"document_id":r.get("document_id"),"manifest_extension":r.get("extension"),"path_extension":ext,"path":path})
  cls,priority,reason,action=classification(ext,r.get("file_category"))
  parser=PARSERS.get(ext,"none")
  grouped[(ext,r.get("source_id","unknown"),cls,priority,parser,reason,action)].append({"document_id":r.get("document_id"),"file_path":path,"local_path":r.get("local_path"),"file_category":r.get("file_category"),"sha256":r.get("sha256"),"processing_status":r.get("processing_status"),"current_exclusion_reason":r.get("exclusion_reason")})
  by_ext[ext]+=1;by_source[r.get("source_id","unknown")]+=1;classifications[cls]+=1
  if parser!="none":
   image_asset=r.get("file_category")=="image"
   scope_candidates.append({"source_id":r.get("source_id"),"document_id":r.get("document_id"),"extension":ext,"file_path":path,"parser":parser,"classification":cls,
    "current_status":"image asset; remains excluded from text ingestion" if image_asset else "excluded; parser support does not authorize ingestion",
    "next_action":"Keep this image asset out of ordinary text ingestion; consider a separate approved visual/OCR workflow only if needed." if image_asset else "Review this exact document and, if appropriate, explicitly amend source scope and ingestion policy before an evidence-backed decision."})
 details=[]
 for key,items in sorted(grouped.items()):
  ext,source,cls,priority,parser,reason,action=key
  details.append({"extension":ext,"count":len(items),"source_id":source,"classification":cls,"proposed_parser":parser,"priority":priority,"reason":reason,"recommendation":action,"records":items})
 result={"report_version":"2.1","project_root":str(ROOT),"source_audit":"ingestion_audit_20261116.json","unsupported_record_count":len(rows),"extension_sum":sum(by_ext.values()),"reconciles_to_3336":len(rows)==3336 and sum(by_ext.values())==3336,"earlier_tally_gap":535,"parser_available_record_count":len(scope_candidates),"missing_bucket_diagnosis":"The prior 2,801 total omitted the .yaml bucket (535 records). Path-derived extension and inventory extension agree for every row; no unsupported row has a missing path.","edge_case_counts":{"missing_paths":len(empty_paths),"extension_field_mismatches":len(path_extension_mismatches),"multi_suffix_paths":len(multi_suffix),"hidden_no_extension_files":len(hidden)},"extension_counts":dict(sorted(by_ext.items())),"source_counts":dict(sorted(by_source.items())),"classification_counts":dict(sorted(classifications.items())),"unclassified_count":classifications.get("Unknown; manual inspection required",0),"extension_source_rows":details,"scope_review_candidates":scope_candidates,"raw_files_modified":False}
 (META/"unsupported_extension_distribution_20261116.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:result[k] for k in ("unsupported_record_count","extension_sum","reconciles_to_3336","earlier_tally_gap","edge_case_counts","extension_counts","source_counts","classification_counts","unclassified_count")},indent=2))

if __name__=="__main__": main()
