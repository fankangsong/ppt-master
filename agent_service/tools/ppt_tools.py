import os
import subprocess
import asyncio
from typing import List, Tuple, Optional, AsyncGenerator

# The path to the scripts directory
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills", "ppt-master", "scripts")

async def run_script_stream_async(script_name: str, args: List[str], cwd: Optional[str] = None) -> AsyncGenerator[str, None]:
    """
    Run a Python script asynchronously and yield its stdout and stderr line by line.
    Works reliably on Windows with uvicorn by running the process in a thread pool.
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    
    if not os.path.exists(script_path):
        yield f"Script not found: {script_path}"
        return

    cmd = ["python", "-u", script_path] + args
    
    try:
        # Instead of asyncio.create_subprocess_exec (which often throws NotImplementedError 
        # on Windows when using Uvicorn due to SelectorEventLoop), we use subprocess.Popen
        # in a thread to stream output line by line safely.
        loop = asyncio.get_running_loop()
        
        def run_proc():
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                text=True,
                bufsize=1
            )
            
        process = await loop.run_in_executor(None, run_proc)
        
        while True:
            # We must use run_in_executor for readline because it's a blocking IO operation
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line:
                break
            yield line.rstrip()
            
        returncode = await loop.run_in_executor(None, process.wait)
        if returncode != 0:
            yield f"Process exited with code {returncode}"
            
    except Exception as e:
        import traceback
        yield f"Execution error: {traceback.format_exc()}"

def run_script(script_name: str, args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Run a Python script from the skills/ppt-master/scripts directory using subprocess.run.
    
    Args:
        script_name: The name of the script to run (e.g., 'project_manager.py' or 'source_to_md/pdf_to_md.py')
        args: A list of string arguments to pass to the script.
        cwd: The working directory to run the script in. If None, uses the current directory.
        
    Returns:
        A tuple of (returncode, stdout, stderr).
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    
    if not os.path.exists(script_path):
        return -1, "", f"Script not found: {script_path}"

    cmd = ["python", script_path] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        import traceback
        return -1, "", traceback.format_exc()


# Project management
def init_project(project_name: str, format: str = "ppt169", projects_dir: str = "projects") -> Tuple[int, str, str]:
    """
    Initialize a new PPT project.
    """
    # The script uses positional argument for project path, or just project name if run from the right cwd
    # Let's pass the full path to the project to be safe, or cd into projects_dir
    project_path = os.path.join(projects_dir, project_name)
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills", "ppt-master", "scripts", "project_manager.py")
    
    # We must run it from the skills/ppt-master/scripts directory because of relative imports in the original script
    cwd = os.path.dirname(script_path)
    
    # The project_manager.py init command expects a name and creates it in its local projects/ directory, 
    # but we want to create it in our global projects dir. Let's pass the absolute path.
    return run_script("project_manager.py", ["init", project_path, "--format", format], cwd=cwd)

def import_sources(project_path: str, sources: List[str], copy: bool = True) -> Tuple[int, str, str]:
    """
    Import source files into a project.
    """
    args = ["import-sources", project_path] + sources
    if copy:
        args.append("--copy")
    else:
        args.append("--move")
    return run_script("project_manager.py", args)

# Document conversion
def parse_pdf(input_path: str, output_path: str) -> Tuple[int, str, str]:
    """
    Convert a PDF file to markdown.
    """
    return run_script("source_to_md/pdf_to_md.py", [input_path, output_path])

def parse_doc(input_path: str, output_path: str) -> Tuple[int, str, str]:
    """
    Convert a DOC/DOCX file to markdown.
    """
    return run_script("source_to_md/doc_to_md.py", [input_path, output_path])

def parse_ppt(input_path: str, output_path: str) -> Tuple[int, str, str]:
    """
    Convert a PPT/PPTX file to markdown.
    """
    return run_script("source_to_md/ppt_to_md.py", [input_path, output_path])

# Image generation
def generate_image(prompt: str, output_dir: str, aspect_ratio: str = "1:1", image_size: str = "1K") -> Tuple[int, str, str]:
    """
    Generate an image using the image_gen.py script.
    """
    args = [
        prompt,
        "--output", output_dir,
        "--aspect_ratio", aspect_ratio,
        "--image_size", image_size
    ]
    return run_script("image_gen.py", args)

# Post-processing
def split_md(project_path: str) -> Tuple[int, str, str]:
    """
    Split the total markdown into individual pages.
    """
    return run_script("total_md_split.py", [project_path])

def finalize_svg(project_path: str) -> Tuple[int, str, str]:
    """
    Finalize SVGs (e.g., embed images, calculate positions).
    """
    return run_script("finalize_svg.py", [project_path])

def generate_pptx(project_path: str, template_path: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Convert SVGs to a final PPTX file.
    """
    args = [project_path]
    if template_path:
        args.extend(["--template", template_path])
    return run_script("svg_to_pptx.py", args)
