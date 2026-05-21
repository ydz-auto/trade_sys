"""Feature Extraction Audit Script"""

import sys
sys.path.insert(0, '.')

from domain.feature.generation_guard import FeatureExtractionAuditor, get_feature_auditor
import importlib
import inspect

def audit_feature_extractors():
    auditor = get_feature_auditor()
    
    feature_modules = [
        "domain.feature.trade.trade_feature",
        "domain.feature.microstructure.microstructure_feature",
        "domain.feature.oi.oi_funding_correlation",
        "domain.feature.liquidation.liquidation_feature",
        "domain.feature.unified_calculator",
        "domain.feature.torch_calculator",
        "domain.feature.generation_service",
    ]
    
    results = {
        "scanned_modules": [],
        "extractor_classes": [],
        "issues": [],
    }
    
    for module_name in feature_modules:
        try:
            module = importlib.import_module(module_name)
            results["scanned_modules"].append({"module": module_name, "status": "ok"})
            
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if "Extractor" in name or "Calculator" in name or "Feature" in name:
                    if obj.__module__ == module_name:
                        audit_result = auditor.audit_extractor_class(obj)
                        audit_result["module"] = module_name
                        results["extractor_classes"].append(audit_result)
                        
                        if audit_result.get("issues"):
                            results["issues"].append({
                                "class": name,
                                "module": module_name,
                                "issues": audit_result["issues"],
                            })
        except Exception as e:
            results["scanned_modules"].append({"module": module_name, "status": "error", "error": str(e)})
            results["issues"].append({
                "module": module_name,
                "error": str(e),
            })
    
    return results

def check_global_statistics():
    issues = []
    
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "\\.mean()\\|\\.std()\\|\\.quantile(", "domain/feature/", "services/research_service/", "research/factor/"],
        capture_output=True,
        text=True,
        cwd="."
    )
    
    lines = result.stdout.strip().split("\n") if result.stdout else []
    
    dangerous_patterns = []
    for line in lines[:50]:
        if "rolling" not in line.lower() and "ewm" not in line.lower() and "expanding" not in line.lower():
            if ".mean()" in line or ".std()" in line or ".quantile(" in line:
                dangerous_patterns.append(line)
    
    return dangerous_patterns[:20]

def check_future_return_usage():
    issues = []
    
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "future_return", "services/", "domain/ml/", "research/"],
        capture_output=True,
        text=True,
        cwd="."
    )
    
    lines = result.stdout.strip().split("\n") if result.stdout else []
    
    for line in lines[:30]:
        if "label" not in line.lower() and "isolated" not in line.lower():
            if "feature" in line.lower() or "merge" in line.lower():
                issues.append(line)
    
    return issues

def main():
    print("=" * 60)
    print("FEATURE EXTRACTION AUDIT REPORT")
    print("=" * 60)
    
    print("\n[1] Auditing Feature Extractor Classes...")
    results = audit_feature_extractors()
    
    print(f"\n  Scanned Modules: {len(results['scanned_modules'])}")
    for m in results['scanned_modules']:
        status = m.get('status', 'unknown')
        print(f"    - {m['module']}: {status}")
    
    print(f"\n  Extractor Classes Found: {len(results['extractor_classes'])}")
    for ec in results['extractor_classes']:
        has_guard = ec.get('has_guard', False)
        issues_count = len(ec.get('issues', []))
        status = "OK" if has_guard or issues_count == 0 else "NEEDS ATTENTION"
        print(f"    - {ec['class_name']}: {status}")
        if ec.get('issues'):
            for issue in ec['issues']:
                print(f"        * {issue}")
    
    print("\n[2] Checking for Global Statistics Usage...")
    dangerous = check_global_statistics()
    if dangerous:
        print(f"  Found {len(dangerous)} potentially dangerous patterns:")
        for d in dangerous[:10]:
            print(f"    - {d[:100]}")
    else:
        print("  No dangerous global statistics patterns found.")
    
    print("\n[3] Checking Future Return Usage...")
    future_issues = check_future_return_usage()
    if future_issues:
        print(f"  Found {len(future_issues)} potential label contamination issues:")
        for fi in future_issues[:10]:
            print(f"    - {fi[:100]}")
    else:
        print("  No label contamination issues found.")
    
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    
    summary = {
        "modules_scanned": len(results['scanned_modules']),
        "extractor_classes": len(results['extractor_classes']),
        "classes_with_issues": len([ec for ec in results['extractor_classes'] if ec.get('issues')]),
        "global_stats_issues": len(dangerous),
        "label_contamination_issues": len(future_issues),
    }
    
    print(f"\nSummary: {summary}")
    return summary

if __name__ == "__main__":
    main()
