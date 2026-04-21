import os

def create_markdown_context(project_root, output_filename="project_context.md"):
    """
    Scans a project directory and compiles all .py files into a structured Markdown document.
    Optimized to walk the directory only once.
    """
    # Comprehensive ignore list for this project
    ignore_dirs = {
        '.git', '__pycache__', 'venv', 'env', '.idea', '.vscode', 
        'node_modules', 'build', 'dist', '.pytest_cache', '.gemini',
        'actions-runner', 'nginx-1.30.0'
    }
    
    architecture_lines = []
    file_contents_sections = []
    
    print(f"Scanning {os.path.abspath(project_root)}...")
    
    for root, dirs, files in os.walk(project_root):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        # Calculate level for tree view
        relative_path = os.path.relpath(root, project_root)
        if relative_path == ".":
            level = 0
            # Use the basename of the absolute path if we are at the root
            folder_name = os.path.basename(os.path.abspath(project_root))
        else:
            level = relative_path.count(os.sep) + 1
            folder_name = os.path.basename(root)
            
        indent = '    ' * level
        architecture_lines.append(f"{indent}📁 {folder_name}/")
        
        subindent = '    ' * (level + 1)
        # Sort files for deterministic output
        for f in sorted(files):
            # Capture only .py files and skip the output file itself
            if f.endswith('.py') and f != os.path.basename(output_filename):
                architecture_lines.append(f"{subindent}📄 {f}")
                
                # Prepare content section
                filepath = os.path.join(root, f)
                rel_filepath = os.path.relpath(filepath, project_root)
                
                content_section = [f"### `{rel_filepath}`", "```python"]
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        code = infile.read()
                        content_section.append(code if code.strip() else "# (File is empty)")
                except Exception as e:
                    content_section.append(f"# [Error reading file: {e}]")
                content_section.append("```\n")
                file_contents_sections.append("\n".join(content_section))

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write("# Project Context\n\n")
        outfile.write("## Architecture\n\n")
        outfile.write("```text\n")
        outfile.write("\n".join(architecture_lines))
        outfile.write("\n```\n\n")
        outfile.write("## File Contents\n\n")
        outfile.write("\n\n".join(file_contents_sections))

    print(f"Success! Context generated at: {output_filename}")
    print(f"Processed {len(file_contents_sections)} Python files.")

if __name__ == "__main__":
    # Run from the project root if the script is in /scripts
    # If the script is run directly, it will scan the current directory
    PROJECT_ROOT = "."
    OUTPUT_FILE = "project_context.md"
    
    create_markdown_context(PROJECT_ROOT, OUTPUT_FILE)
