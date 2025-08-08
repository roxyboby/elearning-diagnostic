#!/usr/bin/env python3
"""
E-Learning Portal Comprehensive Diagnostic Script
This script analyzes the entire application structure, configurations, and potential issues
"""

import os
import sys
import json
import subprocess
import sqlite3
import importlib.util
from pathlib import Path
from datetime import datetime
import traceback

class ELearningDiagnostic:
    def __init__(self, base_path='.'):
        self.base_path = Path(base_path).resolve()
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'base_path': str(self.base_path),
            'issues': [],
            'warnings': [],
            'info': [],
            'file_structure': {},
            'configurations': {},
            'database_status': {},
            'dependencies': {},
            'server_status': {}
        }
    
    def log_issue(self, category, message, severity='error'):
        entry = {
            'category': category,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        if severity == 'error':
            self.report['issues'].append(entry)
        elif severity == 'warning':
            self.report['warnings'].append(entry)
        else:
            self.report['info'].append(entry)
    
    def analyze_file_structure(self):
        """Analyze the complete file structure and identify potential issues"""
        print("🔍 Analyzing file structure...")
        
        expected_files = {
            'app.py': 'Main application file',
            'requirements.txt': 'Python dependencies',
            'wsgi.py': 'WSGI configuration',
            'templates/': 'HTML templates directory',
            'static/': 'Static files directory',
            'instance/': 'Instance-specific files'
        }
        
        # Check for expected files
        for file_path, description in expected_files.items():
            full_path = self.base_path / file_path
            if full_path.exists():
                self.report['file_structure'][file_path] = {
                    'exists': True,
                    'description': description,
                    'size': full_path.stat().st_size if full_path.is_file() else 'directory'
                }
            else:
                self.log_issue('file_structure', f"Missing {description}: {file_path}", 'warning')
                self.report['file_structure'][file_path] = {'exists': False, 'description': description}
        
        # Scan actual directory structure
        for root, dirs, files in os.walk(self.base_path):
            rel_root = Path(root).relative_to(self.base_path)
            if str(rel_root) == '.':
                rel_root = ''
            
            for file in files:
                if file.startswith('.') or file.endswith('.pyc'):
                    continue
                file_path = Path(rel_root) / file if rel_root else Path(file)
                self.report['file_structure'][str(file_path)] = {
                    'exists': True,
                    'size': Path(root, file).stat().st_size,
                    'type': 'file'
                }
    
    def analyze_app_py(self):
        """Analyze the main application file"""
        print("📱 Analyzing app.py...")
        
        app_file = self.base_path / 'app.py'
        if not app_file.exists():
            self.log_issue('app_config', "app.py not found - this is critical!", 'error')
            return
        
        try:
            with open(app_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract key information
            config_info = {
                'flask_imports': 'from flask import' in content,
                'database_config': any(db in content.lower() for db in ['sqlite', 'mysql', 'postgresql']),
                'secret_key': 'SECRET_KEY' in content or 'secret_key' in content,
                'debug_mode': 'debug=True' in content,
                'port_config': 'port=' in content,
                'routes_count': content.count('@app.route'),
                'blueprint_usage': 'Blueprint' in content,
                'error_handling': '@app.errorhandler' in content
            }
            
            self.report['configurations']['app_py'] = config_info
            
            # Check for common issues
            if not config_info['flask_imports']:
                self.log_issue('app_config', "Flask imports not found in app.py", 'error')
            
            if config_info['debug_mode']:
                self.log_issue('app_config', "Debug mode is enabled - should be disabled in production", 'warning')
            
            if not config_info['secret_key']:
                self.log_issue('app_config', "No SECRET_KEY found - sessions won't work properly", 'error')
            
            if config_info['routes_count'] == 0:
                self.log_issue('app_config', "No routes found in app.py", 'warning')
            
            # Try to import and get more details
            self.analyze_app_imports()
            
        except Exception as e:
            self.log_issue('app_config', f"Error reading app.py: {str(e)}", 'error')
    
    def analyze_app_imports(self):
        """Try to import the app and analyze its configuration"""
        print("📦 Analyzing application imports and configuration...")
        
        try:
            # Add current directory to Python path
            sys.path.insert(0, str(self.base_path))
            
            # Try to import the app module
            spec = importlib.util.spec_from_file_location("app", self.base_path / "app.py")
            if spec and spec.loader:
                app_module = importlib.util.module_from_spec(spec)
                
                # This might fail if there are missing dependencies
                try:
                    spec.loader.exec_module(app_module)
                    
                    # Try to get Flask app instance
                    if hasattr(app_module, 'app'):
                        app = app_module.app
                        self.report['configurations']['flask_config'] = {
                            'secret_key_configured': bool(app.config.get('SECRET_KEY')),
                            'database_uri': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured'),
                            'debug': app.config.get('DEBUG', False),
                            'registered_routes': len(app.url_map._rules),
                            'blueprints': list(app.blueprints.keys()) if hasattr(app, 'blueprints') else []
                        }
                        self.log_issue('app_config', "Successfully imported Flask app", 'info')
                    else:
                        self.log_issue('app_config', "No 'app' instance found in app.py", 'error')
                        
                except ImportError as e:
                    self.log_issue('app_config', f"Import error in app.py: {str(e)}", 'error')
                except Exception as e:
                    self.log_issue('app_config', f"Error executing app.py: {str(e)}", 'error')
            
        except Exception as e:
            self.log_issue('app_config', f"Could not analyze app imports: {str(e)}", 'warning')
    
    def analyze_requirements(self):
        """Analyze requirements.txt and check installed packages"""
        print("📋 Analyzing requirements and dependencies...")
        
        req_file = self.base_path / 'requirements.txt'
        if not req_file.exists():
            self.log_issue('dependencies', "requirements.txt not found", 'warning')
            return
        
        try:
            with open(req_file, 'r') as f:
                requirements = f.read().strip().split('\n')
            
            self.report['dependencies']['requirements_file'] = requirements
            
            # Check if packages are installed
            try:
                result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                                      capture_output=True, text=True, cwd=self.base_path)
                installed_packages = result.stdout
                
                missing_packages = []
                for req in requirements:
                    if req.strip() and not req.startswith('#'):
                        package_name = req.split('==')[0].split('>=')[0].split('<=')[0].strip()
                        if package_name.lower() not in installed_packages.lower():
                            missing_packages.append(package_name)
                
                self.report['dependencies']['missing_packages'] = missing_packages
                if missing_packages:
                    self.log_issue('dependencies', f"Missing packages: {', '.join(missing_packages)}", 'error')
                else:
                    self.log_issue('dependencies', "All required packages appear to be installed", 'info')
                    
            except Exception as e:
                self.log_issue('dependencies', f"Could not check installed packages: {str(e)}", 'warning')
                
        except Exception as e:
            self.log_issue('dependencies', f"Error reading requirements.txt: {str(e)}", 'error')
    
    def analyze_database(self):
        """Analyze database configuration and status"""
        print("🗄️ Analyzing database...")
        
        # Look for SQLite databases
        for db_file in self.base_path.rglob('*.db'):
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # Get table information
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                table_info = {}
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    table_info[table] = count
                
                self.report['database_status'][str(db_file.relative_to(self.base_path))] = {
                    'type': 'SQLite',
                    'accessible': True,
                    'tables': table_info
                }
                
                conn.close()
                self.log_issue('database', f"Successfully connected to {db_file.name}", 'info')
                
            except Exception as e:
                self.report['database_status'][str(db_file.relative_to(self.base_path))] = {
                    'type': 'SQLite',
                    'accessible': False,
                    'error': str(e)
                }
                self.log_issue('database', f"Could not access database {db_file.name}: {str(e)}", 'error')
    
    def analyze_templates(self):
        """Analyze template files"""
        print("🎨 Analyzing templates...")
        
        templates_dir = self.base_path / 'templates'
        if not templates_dir.exists():
            self.log_issue('templates', "Templates directory not found", 'error')
            return
        
        template_files = list(templates_dir.rglob('*.html'))
        self.report['configurations']['templates'] = {
            'directory_exists': True,
            'template_count': len(template_files),
            'template_files': [str(f.relative_to(self.base_path)) for f in template_files]
        }
        
        if len(template_files) == 0:
            self.log_issue('templates', "No HTML template files found", 'warning')
        else:
            self.log_issue('templates', f"Found {len(template_files)} template files", 'info')
        
        # Check for common template issues
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for Flask template syntax
                if '{{' not in content and '{%' not in content:
                    self.log_issue('templates', f"{template_file.name} might not be a Flask template", 'warning')
                
            except Exception as e:
                self.log_issue('templates', f"Error reading template {template_file.name}: {str(e)}", 'warning')
    
    def analyze_static_files(self):
        """Analyze static files"""
        print("📁 Analyzing static files...")
        
        static_dir = self.base_path / 'static'
        if not static_dir.exists():
            self.log_issue('static', "Static directory not found", 'warning')
            return
        
        css_files = list(static_dir.rglob('*.css'))
        js_files = list(static_dir.rglob('*.js'))
        img_files = list(static_dir.rglob('*.png')) + list(static_dir.rglob('*.jpg')) + list(static_dir.rglob('*.jpeg')) + list(static_dir.rglob('*.gif'))
        
        self.report['configurations']['static_files'] = {
            'directory_exists': True,
            'css_count': len(css_files),
            'js_count': len(js_files),
            'image_count': len(img_files),
            'css_files': [str(f.relative_to(self.base_path)) for f in css_files],
            'js_files': [str(f.relative_to(self.base_path)) for f in js_files],
            'image_files': [str(f.relative_to(self.base_path)) for f in img_files]
        }
        
        self.log_issue('static', f"Static files: {len(css_files)} CSS, {len(js_files)} JS, {len(img_files)} images", 'info')
    
    def check_server_configuration(self):
        """Check server-related configurations"""
        print("🖥️ Analyzing server configuration...")
        
        # Check WSGI configuration
        wsgi_file = self.base_path / 'wsgi.py'
        if wsgi_file.exists():
            try:
                with open(wsgi_file, 'r') as f:
                    wsgi_content = f.read()
                
                self.report['configurations']['wsgi'] = {
                    'exists': True,
                    'imports_app': 'from app import app' in wsgi_content or 'import app' in wsgi_content,
                    'has_application': 'application = app' in wsgi_content
                }
                
                if not self.report['configurations']['wsgi']['imports_app']:
                    self.log_issue('server', "WSGI file doesn't properly import the app", 'error')
                
            except Exception as e:
                self.log_issue('server', f"Error reading wsgi.py: {str(e)}", 'warning')
        else:
            self.log_issue('server', "wsgi.py not found - needed for production deployment", 'warning')
        
        # Check for Cloudflare tunnel configuration
        if os.path.exists('/etc/cloudflared') or os.path.exists('~/.cloudflared'):
            self.log_issue('server', "Cloudflare tunnel configuration detected", 'info')
        
        # Check if running on Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            if 'Raspberry Pi' in cpuinfo:
                self.log_issue('server', "Running on Raspberry Pi detected", 'info')
        except:
            pass
    
    def check_permissions(self):
        """Check file and directory permissions"""
        print("🔒 Checking permissions...")
        
        important_paths = [
            self.base_path / 'app.py',
            self.base_path / 'static',
            self.base_path / 'templates',
            self.base_path / 'instance'
        ]
        
        for path in important_paths:
            if path.exists():
                stat_info = path.stat()
                # Check if readable by owner
                if not (stat_info.st_mode & 0o400):
                    self.log_issue('permissions', f"File/directory not readable: {path}", 'error')
                # Check if writable by owner for directories that need it
                if path.name in ['instance', 'static'] and not (stat_info.st_mode & 0o200):
                    self.log_issue('permissions', f"Directory not writable: {path}", 'warning')
    
    def generate_solutions(self):
        """Generate solutions based on identified issues"""
        print("💡 Generating solutions...")
        
        solutions = []
        
        # Categorize issues and provide solutions
        for issue in self.report['issues']:
            category = issue['category']
            message = issue['message']
            
            if 'Missing' in message and 'app.py' in message:
                solutions.append({
                    'issue': message,
                    'solution': "Create app.py file with basic Flask application structure",
                    'code_example': """from flask import Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

@app.route('/')
def home():
    return 'Hello World!'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)"""
                })
            
            elif 'SECRET_KEY' in message:
                solutions.append({
                    'issue': message,
                    'solution': "Add SECRET_KEY to your Flask configuration",
                    'code_example': """import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your-secret-key-here'"""
                })
            
            elif 'Missing packages' in message:
                solutions.append({
                    'issue': message,
                    'solution': "Install missing packages using pip",
                    'command': "pip install -r requirements.txt"
                })
            
            elif 'Templates directory not found' in message:
                solutions.append({
                    'issue': message,
                    'solution': "Create templates directory and basic templates",
                    'command': "mkdir templates && touch templates/base.html templates/index.html"
                })
        
        self.report['solutions'] = solutions
    
    def generate_report(self):
        """Generate the final diagnostic report"""
        print("\n" + "="*80)
        print("🎯 E-LEARNING PORTAL DIAGNOSTIC REPORT")
        print("="*80)
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Total Issues: {len(self.report['issues'])}")
        print(f"   • Warnings: {len(self.report['warnings'])}")
        print(f"   • Info Messages: {len(self.report['info'])}")
        
        if self.report['issues']:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in self.report['issues']:
                print(f"   • [{issue['category'].upper()}] {issue['message']}")
        
        if self.report['warnings']:
            print(f"\n⚠️ WARNINGS:")
            for warning in self.report['warnings']:
                print(f"   • [{warning['category'].upper()}] {warning['message']}")
        
        print(f"\n📁 FILE STRUCTURE ANALYSIS:")
        for file_path, info in self.report['file_structure'].items():
            if isinstance(info, dict) and info.get('exists'):
                status = "✅" if info['exists'] else "❌"
                size_info = f" ({info['size']} bytes)" if isinstance(info.get('size'), int) else ""
                print(f"   {status} {file_path}{size_info}")
        
        if self.report['configurations'].get('flask_config'):
            print(f"\n⚙️ FLASK CONFIGURATION:")
            config = self.report['configurations']['flask_config']
            for key, value in config.items():
                print(f"   • {key}: {value}")
        
        if self.report['database_status']:
            print(f"\n🗄️ DATABASE STATUS:")
            for db_path, status in self.report['database_status'].items():
                accessible = "✅" if status.get('accessible') else "❌"
                print(f"   {accessible} {db_path}")
                if status.get('tables'):
                    for table, count in status['tables'].items():
                        print(f"      - {table}: {count} records")
        
        if self.report['solutions']:
            print(f"\n💡 RECOMMENDED SOLUTIONS:")
            for i, solution in enumerate(self.report['solutions'], 1):
                print(f"\n   {i}. Issue: {solution['issue']}")
                print(f"      Solution: {solution['solution']}")
                if 'code_example' in solution:
                    print(f"      Code Example:\n{solution['code_example']}")
                if 'command' in solution:
                    print(f"      Command: {solution['command']}")
        
        # Save detailed report to file
        report_file = self.base_path / 'diagnostic_report.json'
        try:
            with open(report_file, 'w') as f:
                json.dump(self.report, f, indent=2)
            print(f"\n📄 Detailed report saved to: {report_file}")
        except Exception as e:
            print(f"\n❌ Could not save report to file: {e}")
        
        print("\n" + "="*80)
        return self.report
    
    def run_full_diagnostic(self):
        """Run the complete diagnostic process"""
        print("🚀 Starting E-Learning Portal Diagnostic...")
        print(f"📍 Base Path: {self.base_path}")
        print("-" * 80)
        
        try:
            self.analyze_file_structure()
            self.analyze_app_py()
            self.analyze_requirements()
            self.analyze_database()
            self.analyze_templates()
            self.analyze_static_files()
            self.check_server_configuration()
            self.check_permissions()
            self.generate_solutions()
            
            return self.generate_report()
            
        except KeyboardInterrupt:
            print("\n⚠️ Diagnostic interrupted by user")
            return self.report
        except Exception as e:
            print(f"\n❌ Unexpected error during diagnostic: {e}")
            traceback.print_exc()
            return self.report

def main():
    """Main function to run the diagnostic"""
    import argparse
    
    parser = argparse.ArgumentParser(description='E-Learning Portal Diagnostic Tool')
    parser.add_argument('--path', '-p', default='.', help='Path to the e-learning portal directory')
    parser.add_argument('--output', '-o', help='Output file for the report (JSON format)')
    
    args = parser.parse_args()
    
    diagnostic = ELearningDiagnostic(args.path)
    report = diagnostic.run_full_diagnostic()
    
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report also saved to: {args.output}")
        except Exception as e:
            print(f"\n❌ Could not save report to {args.output}: {e}")

if __name__ == "__main__":
    main()