from __future__ import annotations

import ast
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class ModuleInfo:
    file_path: str
    language: str
    imported_libs: Set[Tuple[str, Optional[str]]]


@dataclass
class FunctionInfo:
    id: str
    name: str
    parameters: List[str]
    returns: Optional[str]
    file_path: str
    line: int
    calls: Set[str]


@dataclass
class DeveloperInfo:
    name: Optional[str]
    email: Optional[str]
    team: Optional[str]


def _safe_run_git(args: List[str], cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
        return result.stdout
    except Exception:
        return ""


def discover_developers_for_file(file_path: Path) -> List[DeveloperInfo]:
    # Use git blame to discover emails and names
    cwd = file_path.parent
    output = _safe_run_git(["blame", "--line-porcelain", file_path.name], cwd)
    if not output:
        return []

    emails: Set[str] = set()
    names: Set[str] = set()

    for line in output.splitlines():
        if line.startswith("author "):
            names.add(line[len("author "):].strip())
        elif line.startswith("author-mail "):
            email = line[len("author-mail "):].strip().strip("<>")
            emails.add(email)

    developers: List[DeveloperInfo] = []
    for name in names or {None}:
        # naive mapping: pair any name with any email
        if emails:
            for email in emails:
                developers.append(DeveloperInfo(name=name, email=email, team=None))
        else:
            developers.append(DeveloperInfo(name=name, email=None, team=None))
    if not names and emails:
        for email in emails:
            developers.append(DeveloperInfo(name=None, email=email, team=None))
    return developers


class PythonModuleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.functions: List[FunctionInfo] = []
        self.calls_by_function_stack: List[Set[str]] = []
        self.imports: Set[Tuple[str, Optional[str]]] = set()

    def visit_Import(self, node: ast.Import) -> None:  # type: ignore[override]
        for alias in node.names:
            self.imports.add((alias.name.split(".")[0], None))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # type: ignore[override]
        if node.module:
            self.imports.add((node.module.split(".")[0], getattr(node, "level", None)))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
        param_names = [arg.arg for arg in node.args.args]
        returns = None
        if node.returns is not None:
            returns = ast.unparse(node.returns) if hasattr(ast, "unparse") else None
        func_id = f"{node.name}:{getattr(node, 'lineno', 0)}"
        self.calls_by_function_stack.append(set())
        self.generic_visit(node)
        calls = self.calls_by_function_stack.pop() if self.calls_by_function_stack else set()
        self.functions.append(
            FunctionInfo(
                id=func_id,
                name=node.name,
                parameters=param_names,
                returns=returns,
                file_path="",
                line=getattr(node, "lineno", 0),
                calls=calls,
            )
        )

    def visit_Call(self, node: ast.Call) -> None:  # type: ignore[override]
        # Record simple function name calls: foo(), module.foo()
        name: Optional[str] = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name and self.calls_by_function_stack:
            self.calls_by_function_stack[-1].add(name)
        self.generic_visit(node)


def parse_python_file(file_path: Path) -> Tuple[ModuleInfo, List[FunctionInfo]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)
    visitor = PythonModuleVisitor()
    visitor.visit(tree)
    # attach file path
    for f in visitor.functions:
        f.file_path = str(file_path)
    module = ModuleInfo(file_path=str(file_path), language="python", imported_libs=visitor.imports)
    return module, visitor.functions


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        yield path


def collect_graph_data(root: Path, include_devs: bool = True):
    modules: Dict[str, ModuleInfo] = {}
    functions: List[FunctionInfo] = []
    developers_by_file: Dict[str, List[DeveloperInfo]] = {}
    libraries: Set[str] = set()

    for file_path in iter_source_files(root):
        try:
            module, funcs = parse_python_file(file_path)
        except SyntaxError:
            continue
        modules[module.file_path] = module
        functions.extend(funcs)
        for name, _lvl in module.imported_libs:
            libraries.add(name)
        if include_devs:
            developers_by_file[module.file_path] = discover_developers_for_file(file_path)

    return modules, functions, libraries, developers_by_file


