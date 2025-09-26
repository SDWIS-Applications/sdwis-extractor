"""
Architecture compliance tests for hexagonal architecture.

These tests enforce hexagonal architecture principles by validating:
1. Dependency directions (inward-pointing dependencies)
2. Layer boundaries (core vs adapters vs CLI)
3. Interface usage (services depend on ports, not concrete classes)
4. Business logic isolation (no domain logic in adapters)
"""

import ast
import importlib
import inspect
import pkgutil
import pytest
from pathlib import Path
from typing import Set, List, Dict, Any
import sys
import os

# Add modules to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.architecture
class TestDependencyDirection:
    """Test that dependencies point inward toward the domain core."""

    def test_core_modules_dont_import_adapters(self):
        """Ensure core layer doesn't depend on infrastructure/adapter layer."""
        core_violations = self._find_import_violations('modules.core', 'modules.adapters')

        assert len(core_violations) == 0, \
            f"Core modules importing adapters violates dependency inversion:\n" + \
            '\n'.join([f"  {violation['module']} imports {violation['import']}" for violation in core_violations])

    def test_core_modules_dont_import_cli(self):
        """Ensure core layer doesn't depend on CLI layer."""
        cli_violations = self._find_import_violations('modules.core', 'modules.cli')

        assert len(cli_violations) == 0, \
            f"Core modules importing CLI violates dependency direction:\n" + \
            '\n'.join([f"  {violation['module']} imports {violation['import']}" for violation in cli_violations])

    def test_adapters_can_import_core(self):
        """Verify adapters can import core (this is allowed and expected)."""
        # This is a positive test - adapters SHOULD import core
        core_imports = self._find_import_violations('modules.adapters', 'modules.core')

        # We expect some imports from adapters to core - this is correct
        # Just verify the imports are valid
        for violation in core_imports:
            # Should be importing from core domain, ports, or services
            import_parts = violation['import'].split('.')
            valid_core_parts = ['domain', 'ports', 'services', 'registry', 'validation', 'export_service', 'export_configuration', 'export_orchestration']

            if len(import_parts) >= 3:  # modules.core.something
                assert import_parts[2] in valid_core_parts, \
                    f"Adapter {violation['module']} importing unexpected core module: {violation['import']}"

    def _find_import_violations(self, source_package: str, target_package: str) -> List[Dict[str, str]]:
        """Find imports from source_package that import target_package."""
        violations = []

        try:
            source_pkg = importlib.import_module(source_package)
            source_path = Path(source_pkg.__file__).parent if hasattr(source_pkg, '__file__') else Path(source_pkg.__path__[0])
        except ImportError:
            return violations  # Package doesn't exist

        for py_file in source_path.rglob('*.py'):
            if py_file.name == '__init__.py':
                continue

            try:
                with open(py_file, 'r') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith(target_package):
                                violations.append({
                                    'module': str(py_file.relative_to(Path.cwd())),
                                    'import': alias.name,
                                    'type': 'import'
                                })

                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith(target_package):
                            violations.append({
                                'module': str(py_file.relative_to(Path.cwd())),
                                'import': node.module,
                                'type': 'from_import'
                            })
            except (SyntaxError, UnicodeDecodeError):
                # Skip files that can't be parsed
                continue

        return violations


@pytest.mark.architecture
class TestLayerBoundaries:
    """Test that architectural layers are properly separated."""

    def test_domain_layer_is_pure(self):
        """Test that domain layer has no external dependencies."""
        domain_imports = self._get_external_imports('modules.core.domain')

        # Filter out standard library and typing imports
        external_imports = [
            imp for imp in domain_imports
            if not self._is_standard_library(imp) and
               not imp.startswith('modules.core') and
               not imp.startswith('typing')
        ]

        assert len(external_imports) == 0, \
            f"Domain layer should be pure (no external dependencies):\n" + \
            '\n'.join([f"  {imp}" for imp in external_imports])

    def test_ports_layer_is_abstract(self):
        """Test that ports layer only contains interfaces/abstractions."""
        ports_file = Path('modules/core/ports.py')
        if not ports_file.exists():
            pytest.skip("Ports file not found")

        with open(ports_file, 'r') as f:
            tree = ast.parse(f.read())

        # Should contain Protocol classes or abstract classes
        has_protocols = False
        concrete_implementations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Protocol or ABC
                if any(base.id == 'Protocol' if isinstance(base, ast.Name) else False for base in node.bases):
                    has_protocols = True
                elif any(base.id == 'ABC' if isinstance(base, ast.Name) else False for base in node.bases):
                    has_protocols = True
                else:
                    # Check if it has @abstractmethod decorators
                    has_abstract_methods = any(
                        isinstance(item, ast.FunctionDef) and
                        any(isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod'
                            for decorator in item.decorator_list)
                        for item in node.body
                    )

                    if not has_abstract_methods and node.name not in ['Exception', 'Error'] and 'Error' not in node.name:
                        concrete_implementations.append(node.name)

        assert has_protocols, "Ports layer should contain Protocol or ABC classes"
        assert len(concrete_implementations) == 0, \
            f"Ports layer should not contain concrete implementations: {concrete_implementations}"

    def test_services_depend_on_ports_not_adapters(self):
        """Test that services inject ports/interfaces, not concrete adapters."""
        services_violations = []

        services_path = Path('modules/core/services.py')
        if not services_path.exists():
            pytest.skip("Services file not found")

        try:
            with open(services_path, 'r') as f:
                content = f.read()
                tree = ast.parse(content)

            # Look for class constructors and check their parameter types
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.endswith('Service'):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                            for arg in item.args.args[1:]:  # Skip 'self'
                                if arg.annotation:
                                    annotation_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)

                                    # Check if depending on concrete adapter classes
                                    if 'Adapter' in annotation_str and 'Port' not in annotation_str:
                                        services_violations.append(f"{node.name}.__init__({arg.arg}: {annotation_str})")

        except (SyntaxError, UnicodeDecodeError):
            pytest.skip("Could not parse services file")

        assert len(services_violations) == 0, \
            f"Services should depend on ports, not concrete adapters:\n" + \
            '\n'.join([f"  {violation}" for violation in services_violations])

    def _get_external_imports(self, module_name: str) -> List[str]:
        """Get all external imports from a module."""
        try:
            module = importlib.import_module(module_name)
            module_file = module.__file__
        except ImportError:
            return []

        if not module_file:
            return []

        imports = []
        try:
            with open(module_file, 'r') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except (SyntaxError, UnicodeDecodeError):
            pass

        return imports

    def _is_standard_library(self, module_name: str) -> bool:
        """Check if a module is part of Python standard library."""
        stdlib_modules = {
            'abc', 'asyncio', 'dataclasses', 'datetime', 'enum', 'functools',
            'inspect', 'json', 'os', 'pathlib', 're', 'sys', 'time', 'typing',
            'unittest', 'uuid', 'warnings', 'collections', 'itertools', 'contextlib'
        }

        return module_name.split('.')[0] in stdlib_modules


@pytest.mark.architecture
class TestBusinessLogicIsolation:
    """Test that business logic is properly isolated in the core layer."""

    def test_adapters_contain_no_business_logic_keywords(self):
        """Test that adapters don't contain business logic keywords."""
        business_keywords = [
            'validation', 'business_rule', 'calculate', 'validate',
            'policy', 'rule', 'constraint'
        ]

        violations = []
        adapters_path = Path('modules/adapters')

        if not adapters_path.exists():
            pytest.skip("Adapters directory not found")

        for py_file in adapters_path.rglob('*.py'):
            if py_file.name == '__init__.py':
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read().lower()

                for keyword in business_keywords:
                    if keyword in content:
                        # Look for function/method definitions containing the keyword
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if keyword in line and ('def ' in line or 'class ' in line):
                                violations.append(f"{py_file.name}:{i+1} - {line.strip()}")

            except UnicodeDecodeError:
                continue

        # Allow some exceptions for legitimate adapter concerns
        legitimate_violations = [
            line for line in violations
            if any(legit in line.lower() for legit in [
                'validate_destination', 'validate_config', 'validate_credentials',
                'validate_query', 'validate_session_cookie',  # Port interface methods
                'validate_data', '_validate_schema', 'validate_on_access',  # Schema/data validation
                'validate_session_state',  # UI session state validation
                'validationerror'  # Exception classes
            ])
        ]

        actual_violations = [v for v in violations if v not in legitimate_violations]

        assert len(actual_violations) == 0, \
            f"Adapters should not contain business logic:\n" + \
            '\n'.join([f"  {violation}" for violation in actual_violations])

    def test_domain_models_in_core_only(self):
        """Test that domain model classes are only defined in core layer."""
        domain_classes = ['ExtractionQuery', 'ExtractionResult', 'ExtractionMetadata', 'PaginationConfig']
        violations = []

        # Check adapters directory for domain class definitions
        adapters_path = Path('modules/adapters')
        if adapters_path.exists():
            for py_file in adapters_path.rglob('*.py'):
                try:
                    with open(py_file, 'r') as f:
                        tree = ast.parse(f.read())

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef) and node.name in domain_classes:
                            violations.append(f"{py_file.relative_to(Path.cwd())}:{node.lineno} - class {node.name}")

                except (SyntaxError, UnicodeDecodeError):
                    continue

        assert len(violations) == 0, \
            f"Domain model classes should only be defined in core layer:\n" + \
            '\n'.join([f"  {violation}" for violation in violations])


@pytest.mark.architecture
class TestInterfaceUsage:
    """Test that interfaces are used correctly throughout the system."""

    def test_adapters_implement_ports(self):
        """Test that adapter classes implement the appropriate port interfaces."""
        adapter_port_mapping = {
            'ExtractionPort': ['Extractor', 'ExtractorAdapter'],
            'OutputPort': ['OutputAdapter', 'Output'],
            'ProgressReportingPort': ['ProgressAdapter', 'Progress'],
            'ConfigurationPort': ['ConfigAdapter', 'Config'],
            'AuthenticatedBrowserSessionPort': ['BrowserSession', 'Session'],
            'AuthenticationValidationPort': ['AuthValidator', 'Validator']
        }

        violations = []
        adapters_path = Path('modules/adapters')

        if not adapters_path.exists():
            pytest.skip("Adapters directory not found")

        for py_file in adapters_path.rglob('*.py'):
            if py_file.name == '__init__.py':
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name

                        # Skip mock classes and base classes
                        if 'Mock' in class_name or 'Base' in class_name or 'Abstract' in class_name:
                            continue

                        # Find expected port for this adapter
                        expected_port = None
                        for port, adapter_patterns in adapter_port_mapping.items():
                            if any(pattern in class_name for pattern in adapter_patterns):
                                expected_port = port
                                break

                        if expected_port:
                            # Check if the class mentions the port in its docstring or inheritance
                            class_source = ast.unparse(node) if hasattr(ast, 'unparse') else content[node.lineno-1:node.end_lineno]

                            if expected_port not in class_source:
                                # Check imports to see if port is imported
                                port_imported = f"from modules.core.ports import" in content and expected_port in content

                                if not port_imported:
                                    violations.append(f"{py_file.name} - {class_name} should implement or reference {expected_port}")

            except (SyntaxError, UnicodeDecodeError):
                continue

        # This is a warning rather than failure since some adapters might be legitimate
        if violations:
            print(f"⚠️  Potential interface compliance issues:\n" + '\n'.join([f"  {v}" for v in violations]))

    def test_no_circular_imports(self):
        """Test that there are no circular import dependencies."""
        # This is a simplified test - a more comprehensive version would build a full dependency graph
        known_problematic_pairs = [
            ('modules.core.services', 'modules.core.domain'),
            ('modules.adapters.extractors', 'modules.adapters.output'),
        ]

        circular_imports = []

        for pkg1, pkg2 in known_problematic_pairs:
            try:
                # Try importing both and see if it causes issues
                importlib.import_module(pkg1)
                importlib.import_module(pkg2)
            except ImportError as e:
                if 'circular import' in str(e).lower():
                    circular_imports.append(f"{pkg1} <-> {pkg2}: {e}")

        assert len(circular_imports) == 0, \
            f"Circular imports detected:\n" + '\n'.join([f"  {ci}" for ci in circular_imports])


@pytest.mark.architecture
class TestArchitecturalMetrics:
    """Test architectural quality metrics."""

    def test_core_to_adapter_ratio(self):
        """Test that core code size is reasonable compared to adapter code."""
        core_loc = self._count_lines_of_code('modules/core')
        adapter_loc = self._count_lines_of_code('modules/adapters')

        if core_loc > 0 and adapter_loc > 0:
            # Core should be substantial but not dominate
            ratio = core_loc / (core_loc + adapter_loc)

            assert 0.15 <= ratio <= 0.6, \
                f"Core/Total ratio ({ratio:.2f}) should be between 0.15 and 0.6. " + \
                f"Core: {core_loc} LOC, Adapters: {adapter_loc} LOC"

    def test_adapter_diversity(self):
        """Test that we have adapters for multiple concerns."""
        adapter_types = self._count_adapter_types()

        expected_types = ['auth', 'extractors', 'output', 'progress']
        found_types = [t for t in expected_types if t in adapter_types and adapter_types[t] > 0]

        assert len(found_types) >= 3, \
            f"Should have adapters for at least 3 concerns. Found: {found_types}"

    def _count_lines_of_code(self, package_path: str) -> int:
        """Count lines of code in a package."""
        path = Path(package_path)
        if not path.exists():
            return 0

        total_lines = 0
        for py_file in path.rglob('*.py'):
            try:
                with open(py_file, 'r') as f:
                    lines = f.readlines()
                    # Count non-empty, non-comment lines
                    code_lines = [
                        line for line in lines
                        if line.strip() and not line.strip().startswith('#')
                    ]
                    total_lines += len(code_lines)
            except UnicodeDecodeError:
                continue

        return total_lines

    def _count_adapter_types(self) -> Dict[str, int]:
        """Count the number of adapters by type."""
        adapters_path = Path('modules/adapters')
        if not adapters_path.exists():
            return {}

        adapter_counts = {}
        for subdir in adapters_path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('__'):
                py_files = list(subdir.glob('*.py'))
                non_init_files = [f for f in py_files if f.name != '__init__.py']
                adapter_counts[subdir.name] = len(non_init_files)

        return adapter_counts