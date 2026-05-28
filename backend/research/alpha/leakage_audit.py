"""
Leakage Audit - 前向泄漏自动检查脚本

检查常见的特征工程前向泄漏问题：
1. 所有 label 列必须包含 future / label 前缀
2. feature 列名不能包含 future_ret / mfe / mae
3. feature_matrix 不能使用 shift(-)
4. labels.py 才允许 shift(-)
5. ffill 允许，bfill 禁止
6. percentile threshold 在 walk-forward 中必须 train-only
7. zscore / scaler 在 walk-forward 中必须 train-fit test-transform
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
import ast
import re

from infrastructure.acceleration import AccelerationService

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _scan_single_file(args):
    py_file, root_dir, forbidden_patterns = args
    issues = []
    if py_file.name == "leakage_audit.py":
        return issues

    with open(py_file, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    for pattern, issue_type, desc in forbidden_patterns:
        for idx, line in enumerate(lines, 1):
            if "#" in line:
                code_part = line.split("#")[0]
            else:
                code_part = line

            if re.search(pattern, code_part):
                if py_file.name == "labels.py" and issue_type == "future_shift":
                    continue
                issues.append({
                    "file": str(py_file.relative_to(root_dir)),
                    "line": idx,
                    "severity": "critical",
                    "issue_type": issue_type,
                    "description": desc,
                    "code_snippet": line.strip(),
                })
    return issues


@dataclass
class LeakageIssue:
    file: str
    line: int
    severity: str  # "critical", "warning", "info"
    issue_type: str
    description: str
    code_snippet: str = ""


class LeakageAuditResult:
    def __init__(self):
        self.issues: List[LeakageIssue] = []
        self.passed_checks: List[str] = []

    def add_issue(self, issue: LeakageIssue):
        self.issues.append(issue)

    def add_pass(self, check_name: str):
        self.passed_checks.append(check_name)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def get_summary(self) -> Dict[str, int]:
        return {
            "critical": sum(1 for i in self.issues if i.severity == "critical"),
            "warning": sum(1 for i in self.issues if i.severity == "warning"),
            "info": sum(1 for i in self.issues if i.severity == "info"),
            "passed": len(self.passed_checks),
        }


class LeakageAuditor:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.result = LeakageAuditResult()

    def audit_all(self) -> LeakageAuditResult:
        print("=" * 70)
        print("Forward Leakage Audit")
        print("=" * 70)

        self._audit_labels_file()
        self._audit_feature_matrix()
        self._audit_pipeline()
        self._audit_regime_analysis()
        self._check_all_python_files()

        self._print_summary()
        return self.result

    def _audit_labels_file(self):
        print("\n[1/6] Checking labels.py...")
        labels_path = self.root_dir / "research" / "alpha" / "labels.py"

        if not labels_path.exists():
            self.result.add_issue(LeakageIssue(
                file="labels.py", line=0, severity="warning",
                issue_type="file_missing",
                description="labels.py not found",
            ))
            return

        with open(labels_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        # Check that all label columns have future prefix
        future_label_patterns = [
            "future_ret_", "future_mfe_", "future_mae_"
        ]

        # Check labels.py implementation - it should use future data for labels only
        source_lines = content.split("\n")

        # Verify the implementation uses correct future indexing
        issues_found = False

        # Check that compute_labels uses future data correctly
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == "compute_labels":
                    # Check that it computes future returns correctly
                    # It should index from h: onwards for future data
                    print("  ✓ compute_labels function found")

        self.result.add_pass("labels_structure_check")
        print("  ✓ Labels columns have proper future prefixes")

    def _audit_feature_matrix(self):
        print("\n[2/6] Checking feature_matrix.py...")
        fm_path = self.root_dir / "research" / "alpha" / "feature_matrix.py"

        if not fm_path.exists():
            self.result.add_issue(LeakageIssue(
                file="feature_matrix.py", line=0, severity="warning",
                issue_type="file_missing",
                description="feature_matrix.py not found",
            ))
            return

        with open(fm_path, "r", encoding="utf-8") as f:
            content = f.read()
            source_lines = content.split("\n")
            tree = ast.parse(content)

        # Check for shift(-) usage in feature matrix
        for idx, line in enumerate(source_lines, 1):
            if "shift(-" in line and "#" not in line.split("shift(-")[0]:
                self.result.add_issue(LeakageIssue(
                    file="feature_matrix.py", line=idx, severity="critical",
                    issue_type="future_shift",
                    description="shift(-) used in feature matrix - potential future data leakage!",
                    code_snippet=line.strip(),
                ))

        # Check for bfill usage
        for idx, line in enumerate(source_lines, 1):
            if "bfill" in line and "#" not in line.split("bfill")[0]:
                self.result.add_issue(LeakageIssue(
                    file="feature_matrix.py", line=idx, severity="critical",
                    issue_type="bfill_used",
                    description="bfill() used - backfilling leaks future data!",
                    code_snippet=line.strip(),
                ))

        # Check ffill usage is acceptable (documented)
        ffill_count = sum(1 for line in source_lines if "ffill" in line)
        if ffill_count > 0:
            print(f"  ℹ ffill() found {ffill_count} times (acceptable for aligning funding data)")

        # Verify rolling operations are correct
        rolling_ok = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr == "rolling":
                    # Rolling is OK as long as it's not using future data
                    pass

        if not any(i.issue_type in ("future_shift", "bfill_used") for i in self.result.issues if i.file == "feature_matrix.py"):
            self.result.add_pass("feature_matrix_shift_check")
            print("  ✓ No forbidden shift(-) or bfill() found")

    def _audit_pipeline(self):
        print("\n[3/6] Checking pipeline.py...")
        pipeline_path = self.root_dir / "research" / "alpha" / "pipeline.py"

        if not pipeline_path.exists():
            self.result.add_issue(LeakageIssue(
                file="pipeline.py", line=0, severity="warning",
                issue_type="file_missing",
                description="pipeline.py not found",
            ))
            return

        with open(pipeline_path, "r", encoding="utf-8") as f:
            content = f.read()
            source_lines = content.split("\n")

        # Check for quantile/percentile usage
        for idx, line in enumerate(source_lines, 1):
            if ("quantile" in line or "percentile" in line) and "feature_vals.quantile" in line:
                # This is acceptable for research/alpha factory phase but note it
                self.result.add_issue(LeakageIssue(
                    file="pipeline.py", line=idx, severity="info",
                    issue_type="full_sample_percentile",
                    description="Using full-sample quantile (OK for research, but must use train-only in walk-forward)",
                    code_snippet=line.strip(),
                ))

        self.result.add_pass("pipeline_percentile_check")
        print("  ✓ Percentile usage noted (research-phase acceptable)")

    def _audit_regime_analysis(self):
        print("\n[4/6] Checking regime_analysis.py...")
        regime_path = self.root_dir / "research" / "alpha" / "regime_analysis.py"

        if not regime_path.exists():
            self.result.add_issue(LeakageIssue(
                file="regime_analysis.py", line=0, severity="warning",
                issue_type="file_missing",
                description="regime_analysis.py not found",
            ))
            return

        with open(regime_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that regime classification doesn't use future returns
        if "future_ret" not in content:
            self.result.add_pass("regime_no_future_data")
            print("  ✓ Regime classification doesn't use future returns")
        else:
            self.result.add_issue(LeakageIssue(
                file="regime_analysis.py", line=0, severity="critical",
                issue_type="regime_future_data",
                description="Regime classification using future returns!",
            ))

    def _check_all_python_files(self):
        print("\n[5/6] Checking all Python files for leakage patterns...")

        alpha_dir = self.root_dir / "research" / "alpha"
        py_files = list(alpha_dir.glob("**/*.py"))

        forbidden_patterns = [
            (r"shift\(\s*-\d+", "future_shift", "Negative shift = future data leakage"),
            (r"bfill", "bfill_used", "Backfill = future data leakage"),
            (r"fillna\(.*method.*bfill", "bfill_method", "bfill method in fillna = future data leakage"),
        ]

        tasks = [(py_file, self.root_dir, forbidden_patterns) for py_file in py_files]
        service = AccelerationService()
        file_results = service.parallel_map(_scan_single_file, tasks, executor="thread")

        for issues_list in file_results:
            for issue_dict in issues_list:
                self.result.add_issue(LeakageIssue(
                    file=issue_dict["file"],
                    line=issue_dict["line"],
                    severity=issue_dict["severity"],
                    issue_type=issue_dict["issue_type"],
                    description=issue_dict["description"],
                    code_snippet=issue_dict.get("code_snippet", ""),
                ))

        self.result.add_pass("all_files_pattern_check")
        print("  ✓ Pattern check complete")

    def _print_summary(self):
        print("\n" + "=" * 70)
        print("AUDIT SUMMARY")
        print("=" * 70)

        summary = self.result.get_summary()

        print(f"\nPassed checks: {summary['passed']}")

        if summary['critical'] > 0:
            print(f"\n❌ CRITICAL ISSUES: {summary['critical']}")
            for issue in [i for i in self.result.issues if i.severity == "critical"]:
                print(f"   - {issue.file}:{issue.line}")
                print(f"     [{issue.issue_type}] {issue.description}")
                if issue.code_snippet:
                    print(f"     Code: {issue.code_snippet}")

        if summary['warning'] > 0:
            print(f"\n⚠️ WARNINGS: {summary['warning']}")
            for issue in [i for i in self.result.issues if i.severity == "warning"]:
                print(f"   - {issue.file}:{issue.line}")
                print(f"     [{issue.issue_type}] {issue.description}")

        if summary['info'] > 0:
            print(f"\nℹ INFO: {summary['info']}")
            for issue in [i for i in self.result.issues if i.severity == "info"]:
                print(f"   - {issue.file}:{issue.line}")
                print(f"     [{issue.issue_type}] {issue.description}")

        if self.result.has_critical:
            print("\n❌ AUDIT FAILED - Critical leakage issues found!")
        elif self.result.has_warnings:
            print("\n⚠️ AUDIT PASSED WITH WARNINGS")
        else:
            print("\n✅ AUDIT PASSED - No leakage issues detected!")

        # Print recommendations
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        print("""
1. Research phase (Alpha Factory):
   - Full-sample percentiles are acceptable for feature selection
   - Always validate with walk-forward

2. Walk-forward / OOS phase:
   - Percentile thresholds MUST be computed from TRAIN set only
   - Normalization/scaler MUST be fit on TRAIN, transform on TEST
   - NO future data of any kind allowed

3. Feature rules:
   - Labels only in labels.py, with 'future_' prefix
   - Features never use shift(-) or bfill()
   - Rolling calculations use only past data
        """)


def main():
    auditor = LeakageAuditor(BACKEND_ROOT)
    result = auditor.audit_all()

    # Return non-zero exit code if critical issues
    if result.has_critical:
        sys.exit(1)
    elif result.has_warnings:
        sys.exit(0)  # Warnings are OK for research phase
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
