import csv
import sys
import os
import git
import get_uniq_projects
import openai
import datetime
import glob
import utils
import tiktoken
import subprocess
import javalang
from subprocess import Popen, PIPE
import re

run_test_cmds = "/home/azureuser/flaky/cmds/run_test.sh"
run_nondex_cmds = "/home/azureuser/flaky/cmds/run_nondex.sh"
run_surefire_cmds = "/home/azureuser/flaky/cmds/run_surefire.sh"
checkout_project_cmds = "/home/azureuser/flaky/cmds/checkout_project.sh"
restore_project_cmds = "/home/azureuser/flaky/cmds/stash_project.sh"

def match_import(response):
    print(response)
    # import_pattern = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)
    # import_pattern = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)
    # import_pattern = re.compile(r'import\s+([\w.]+);')
    import_pattern = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)
    # import_pattern = re.compile(r'^(import\s+[\w.]+;)', re.MULTILINE)
    imp_matches = import_pattern.findall(response)
    print(imp_matches)

def git_stash(project, sha, cloneDir,file_path):
    result = subprocess.run(["bash",checkout_project_cmds,project,sha,cloneDir,file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    print(output,flush = True)

def restore_project(project, sha, cloneDir):
    result = subprocess.run(["bash",restore_project_cmds,project,sha,cloneDir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    print(output,flush = True)

def match_patch(response):
    if ("<class changed>") in response:
        if ("}") in response:
            right_idx = response.rindex("}")
            if ("package ") in response: # whole class file in the answer
                left_idx = response.index("package ")
                potential_patch = response[left_idx:right_idx+1]
                return potential_patch,0
            else: # only test method in the answer
                if ("@Test") in response:
                    left_idx = response.index("@Test")
                    potential_patch = response[left_idx:right_idx+1]
                    return potential_patch,1
                if ("public void ") in response:
                    left_idx = response.index("public void ")
                    potential_patch = response[left_idx:right_idx+1]
                    return potential_patch,1
                
    if ("<method changed>") in response:
        if ("}") in response:
            right_idx = response.rindex("}")
            if ("@Test") in response:
                left_idx = response.index("@Test")
                potential_patch = response[left_idx:right_idx+1]
                return potential_patch,1
            if ("public void ") in response:
                left_idx = response.index("public void ")
                potential_patch = response[left_idx:right_idx+1]
                return potential_patch,1
    return None,None

def replace_last(source_string, replace_what, replace_with):
    head, _sep, tail = source_string.rpartition(replace_what)
    return head + replace_with + tail

def apply_patch(project,sha,module,test,test_type,method_name,patch,patch_type,file_path,cloneDir):
    format_test = replace_last(test, '.', '#')
    
    if patch == None:
        print("[ERROR]No Patch",flush = True)
        return None
    try:
        if patch_type == 1: #only change method
            file = open(file_path, 'r', errors='ignore')
            class_content = file.read()
            res = utils.get_test_method(method_name, class_content) #res = [start,end,method_name,method_code,node.annotations]
            if res == None:
                return None
            method_code = res[3]
            annotations = res[4]
            new_patch = patch
            for annotation in annotations:
                if "@"+annotation.name in patch:
                    new_patch = patch.replace("@" + annotation.name, "")
            fixed_class = class_content.replace(method_code,new_patch)
            

            print(("[Before fix] Running test {} with type {} from project {} sha {} module {} \
                ").format(format_test, test_type, project, sha, module),flush = True)
            git_stash(project, sha, cloneDir,file_path)
            verify_by_tool(test_type,project,sha,format_test,module,cloneDir,"BeforeFix")

            print(("[Applying FIX] Applying patch on test {}").format(format_test),flush = True)
            f = open(file_path, "w", errors='ignore')
            f.write(fixed_class)
            f.close()

            print(("[After fix] Running test {} with type {} from project {} sha {} module {} \
                    ").format(format_test, test_type, project, sha, module),flush = True)
            verify_by_tool(test_type,project,sha,format_test,module,cloneDir,"AfterFix")
            git_stash(project, sha, cloneDir,file_path)

            return new_patch

        if patch_type == 0:

            print(("[Before fix] Running test {} with type {} from project {} sha {} module {} \
                ").format(format_test, test_type, project, sha, module),flush = True)
            git_stash(project, sha, cloneDir,file_path)
            verify_by_tool(test_type,project,sha,format_test,module,cloneDir,"BeforeFix")

            print(("[Applying FIX] Applying patch on test {}\n").format(format_test),flush = True)

            f = open(file_path, "w", errors='ignore')
            f.write(patch)
            f.close()

            print(("[After fix] Running test {} with type {} from project {} sha {} module {} \
                    ").format(format_test, test_type, project, sha, module),flush = True)
            verify_by_tool(test_type,project,sha,format_test,module,cloneDir,"AfterFix")
            git_stash(project, sha, cloneDir,file_path)
            # exit(0)
            return patch
    except:
        return None

def verify_by_tool(test_type,project,sha,format_test,module,cloneDir,tag,times):
    if test_type == "ID" or test_type == "NOD":
        print(("RUNNING NonDex {} time(s) on test {} with type {} from project {} sha {} module {} \
              ").format(times, format_test, test_type, project, sha, module),flush = True)
        output = run_nondex(project,sha,format_test,module,cloneDir,tag,times)
        return output
    if test_type == "Brit":
        print(("RUNNING NonDex {} time(s) on test {} with type Brit from project {} sha {} module {} \
              ").format(times, format_test, test_type, project, sha, module),flush = True)
        output = run_nondex(project,sha,format_test,module,cloneDir,tag,times)
        return output


#(test_type,project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times,victim_file_path)
def verify_by_surefire(test_type,project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times): 
    if "OD" in test_type:
        print(("RUNNING Surefire {} time(s) on polluter {} and victim {} with type {} from project {} sha {} module {} \
              ").format(times,polluter_format_test,victim_format_test, test_type, project, sha, module),flush = True)
        output = run_surefire(project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times)
        return output
    
def run_nondex(project,sha,test,module,cloneDir,tag,times):
    result = subprocess.run(["bash",run_nondex_cmds,project,sha,test,module,cloneDir,tag,times], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    print(output,flush = True)
    return output

def run_surefire(project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times):
    result = subprocess.run(["bash",run_surefire_cmds,project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    print(output,flush = True)
    return output
