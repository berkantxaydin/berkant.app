import os

def create_markdown_context(project_root, output_filename="project_context.md"):
    # Comprehensive ignore list for this project
    ignore_dirs = {
        '.git', '__pycache__', 'venv', 'env', '.idea', '.vscode', 
        'node_modules', 'build', 'dist', '.pytest_cache', '.gemini',
        'actions-runner', 'nginx-1.30.0'
    }

    readable_extensions = ('.py', '.html', '.js', '.css')
    
    architecture_lines = []
    file_contents_sections = []
    
    print(f"Scanning {os.path.abspath(project_root)}...")
    
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        relative_path = os.path.relpath(root, project_root)
        if relative_path == ".":
            level = 0
            folder_name = os.path.basename(os.path.abspath(project_root))
        else:
            level = relative_path.count(os.sep) + 1
            folder_name = os.path.basename(root)
            
        indent = '    ' * level
        architecture_lines.append(f"{indent}📁 {folder_name}/")
        
        subindent = '    ' * (level + 1)
        for f in sorted(files):
            # 1. ALWAYS add the file to the architecture map (so I can see it)
            if f != os.path.basename(output_filename):
                architecture_lines.append(f"{subindent}📄 {f}")
                
                # 2. ONLY read the contents if it's a code/text file
                if f.endswith(readable_extensions):
                    filepath = os.path.join(root, f)
                    rel_filepath = os.path.relpath(filepath, project_root)
                    
                    # Markdown language tagging
                    lang = "python" if f.endswith('.py') else "html" if f.endswith('.html') else "text"
                    
                    content_section = [f"### `{rel_filepath}`", f"```{lang}"]
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            code = infile.read()
                            content_section.append(code if code.strip() else "# (File is empty)")
                    except Exception as e:
                        content_section.append(f"")
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
    print(f"Read code from {len(file_contents_sections)} files.")

if __name__ == "__main__":
    PROJECT_ROOT = "."
    OUTPUT_FILE = "project_context.md"
    create_markdown_context(PROJECT_ROOT, OUTPUT_FILE)