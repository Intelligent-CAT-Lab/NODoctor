import javalang
from typing import Set, Tuple
import sys
import re
import csv
import os
import subprocess

checkout_project_cmds = "scripts/cmds/checkout_project.sh"
stash_project_cmds = "scripts/cmds/stash_project.sh"
run_nondex_cmds = "scripts/cmds/run_nondex.sh"

def extract_nondex_result(entry, clone_dir):
    sha = entry['SHA Detected']
    repo_name = entry['repo_name']
    module = entry['Module Path']
    test_full_name = entry['Fully-Qualified Test Name (packageName.ClassName.methodName)']
    test_file_path = entry['test_file_path']
    repo_path = os.path.join(clone_dir, sha, repo_name)
    output = run_test_with_nondex(repo_path, module, test_full_name)
    summary, msg = None, None
    summary, msg = analyze_nondex_result(output)
    add_err_msg, err_code = get_err_code_list(output, test_full_name, test_file_path)
    print(test_file_path)
    final_err_msg = f'{msg}\n{add_err_msg}'.replace('\n', '  ')
    final_err_code = '\n'.join(err_code)
    
    err_method_names = get_err_method_names(output, test_file_path, test_full_name)
    return summary, final_err_msg, final_err_code, err_method_names

def parse_err_msg(output):
    msgs = []
    for line in output.split('\n'):
        if line.startswith('[ERROR]'):
            clean_line = line.strip().replace('[ERROR]', '')
            if 'Time elapsed' in line or 'There are test failures' in line or 'Skipped:' in line:
                continue
            if clean_line not in msgs:
                msgs.append(clean_line)
    return '\n'.join(msgs)
    
def analyze_nondex_result(output):
    result = None
    if 'There are test failures' in output:
        err_msg = parse_err_msg(output)
        return 'FAILURE', err_msg
    elif 'BUILD SUCCESS' in output and 'No Test Failed with this configuration' in output:
        return "PASS", None
    else:
        # print(output)
        exit(0)
        

from bs4 import BeautifulSoup
from pathlib import Path
        
def get_err_code_list(output, test_full_name, test_file_path):
    test_class_content = read_java(test_file_path)
    test_method_name = test_full_name.split(".")[-1]
    test_class = test_full_name.replace(f'.{test_method_name}', '')
    err_msg_list = [] 
    err_code_list = []
    lineno_list = []
    class_file = test_full_name.split(".")[-2] + ".java"
    if "COMPILATION ERROR" in output:
        err_msg_list, err_code_list = parse_compilation_err(output, test_full_name, test_class_content)
        return err_msg_list, err_code_list

    for output_line in output.split("\n"):
        lineno = None
        if class_file in output_line:
            lineno_str = str(output_line).split(class_file + ":")[-1].split(")")[0]
            try:
                lineno = int(lineno_str)
            except:
                pass
        if class_file in output_line and "[" in output_line and "]" in output_line:
            lineno_str = str(output_line).split(class_file + ":")[-1].split("[")[-1].split(",")[0].split("]")[0]
            try:
                lineno = int(lineno_str)
            except:
                pass
        if lineno != None and lineno not in lineno_list:
            lineno_list.append(lineno)

    for number in lineno_list:
        err_code = test_class_content.split("\n")[int(number)-1]
        if err_code.strip() not in err_code_list:
            err_code_list.append(err_code.strip())

    for line in output.split("\n"):
        if "Please refer to" in line and "for the individual test results" in line:
            xml_dir = line.split("Please refer to")[-1].split("for")[0].strip()
            for root, dirs, files in os.walk(xml_dir):
                for file in files:
                    if file.endswith(".xml") and "TEST-" + test_class in file:
                        xml_path = os.path.join(root, file)
                        with open(xml_path, 'r') as f:
                            data = f.read()
                        bs_data = BeautifulSoup(data, 'xml')
                        for tag in bs_data.find_all('testcase', {'classname':test_class}, {'name':test_method_name}):
                            err_element = tag.find('error')
                            if err_element:
                                err_msg = err_element.get('message')
                                err_type = err_element.get('type')
                                if err_msg == None:
                                    err_msg = err_type
                                final_err_msg = ' '.join(err_msg.split())
                                if final_err_msg not in err_msg_list:
                                    err_msg_list.append(final_err_msg.strip())
                                
                            failure_element = tag.find('failure')
                            if failure_element:
                                failure_msg = failure_element.get('message')
                                failure_type = failure_element.get('type')
                                if failure_msg == None:
                                    failure_msg = failure_type
                                final_failure_msg = ' '.join(failure_msg.split())
                                if final_failure_msg not in err_msg_list:
                                    err_msg_list.append(final_failure_msg.strip())
                            
    return '\n'.join(err_msg_list), err_code_list

def parse_compilation_err(output, test_full_name, test_file_path):
    test_class_content = read_java(test_file_path)
    class_file = test_full_name.split(".")[-2] + ".java"
    err_code_list = []
    lineno_list = []
    for output_line in output.split("\n"):
        lineno = None
        if class_file in output_line:
            lineno_str = str(output_line).split(class_file + ":")[-1].split(")")[0]
            try:
                lineno = int(lineno_str)
            except:
                pass
        if class_file in output_line and "[" in output_line and "]" in output_line:
            lineno_str = str(output_line).split(class_file + ":")[-1].split("[")[-1].split(",")[0].split("]")[0]
            try:
                lineno = int(lineno_str)
            except:
                pass
        if lineno != None and lineno not in lineno_list:
            lineno_list.append(lineno)
    for number in lineno_list:
        err_code = test_class_content.split("\n")[int(number)-1]
        if err_code.strip() not in err_code_list:
            err_code_list.append(err_code.strip())
    
    seq = output.split("[INFO] Finished at:")[-1].split("To see the full stack trace of the errors")[0].replace("-> [Help 1]", "")
    for line in seq.split("\n"):
        if "Failed to execute goal" in line:
            continue
        if not line.startswith("[ERROR]"):
            continue
        tmp_line = line.replace("[ERROR]","").strip()
        if class_file in tmp_line:
            msg = tmp_line.split("]")[-1]
            if msg not in err_msgs:
                err_msgs.append(msg)
        else:
            if tmp_line not in err_msgs:
                err_msgs.append(tmp_line)
    return '\n'.join(err_msgs), err_code_list
    

def run_test_with_nondex(project_dir, module, test_full_name, jdk='8', nondex_times='4'):
    test = replace_last_symbol(test_full_name, ".", "#")
    result = subprocess.run(["bash", run_nondex_cmds, project_dir, module, test, jdk, nondex_times], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    # print(output)
    return output

def replace_last_symbol(source_string, replace_what, replace_with):
    head, _sep, tail = source_string.rpartition(replace_what)
    return head + replace_with + tail


def locate_test_code(potential_test_file, test_full_name):
    java_code = read_java(potential_test_file)
    method_name = test_full_name.split('.')[-1]
    test_code = None
    test_code = get_test_method(method_name, java_code)
    return test_code

def git_checkout_file(projectDir,file_path):
    print(f'* Git checkout {file_path} in {projectDir}')
    result = subprocess.run(["bash",checkout_project_cmds,projectDir,file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    print(f'* {output}')

def read_csv(filepath):
    data = []
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(row)
    return data

def get_file_lists(repo_path, test_full_name, module):
    potential_file_paths = []
    test_class_short_name = test_full_name.split('.')[-2]
    test_class_path = "/".join(test_full_name.split('.')[:-1])
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if not file.endswith(test_class_short_name + ".java"):
                continue
            file_path = os.path.join(root, file)
            if test_class_path in file_path and module in file_path \
                 and "/test/" in file_path.lower():
                    potential_file_paths.append(file_path)
    return potential_file_paths


def get_test_files(test_full_name, clone_dir, repo_name, sha, module):
    repo_path = os.path.join(clone_dir, sha, repo_name)
    potential_file_paths = get_file_lists(repo_path, test_full_name, module)
    return potential_file_paths
    
def get_realted_helper(file_path):
    java_code = read_java(file_path)
    helper_methods = get_helper_methods(java_code)
    global_vars = get_global_vars(java_code)
    return helper_methods, global_vars

def get_helper_methods(code):
    method_list = parse_java_func_intervals(code)
    start_lines = []
    res = {"before":{},"after":{},"earlist_line":{},"helper_method_names":[]}
    for method_info in method_list:
        start, end, method_name, method_code, node = method_info[0:]
        start_lines.append(start.line)
        if node.annotations != None:
            for ele in node.annotations:
                if ele.name == "BeforeClass" or ele.name == "Before" or ele.name == "BeforeAll":
                    if method_name not in res["before"]:
                        method_code = get_string(code,start,end)
                        res["before"][method_name] = method_code
                        res["helper_method_names"].append(method_name)
                elif ele.name == "AfterClass" or ele.name == "After" or ele.name == "AfterAll":
                    if method_name not in res["after"]:
                        method_code = get_string(code,start,end)
                        res["after"][method_name] = method_code
                        res["helper_method_names"].append(method_name)
    res["earlist_line"] = min(start_lines)
    return res


def get_err_method_names(nondex_output,test_file_path,test_full_name):
    # print("get_line_caused_errors")
    output_seq = nondex_output.split("\n")
    test_class = test_file_path.split("/")[-1]
    test_class_name = '.'.join(test_full_name.split(".")[:-1])

    s_list = nondex_output.split("<<< FAILURE!")[1:]

    line_nums = []
    res_lines = []
    method_names = []

    for seq in output_seq:
        if "\tat " in seq:
            lines_info = (seq.split("\tat", 1)[1]).split("\n")
            for line in lines_info:
                if test_class_name in line and ":" in line and ")" in line:
                    num = (line.split(":")[1]).split(")")[0]
                    if num not in line_nums:
                        line_nums.append(num)
                    if test_class_name+"." in line:
                        new_line = line.replace(" ","")
                        method_name = new_line.split("(")[0].replace(test_class_name+".","")
                        if method_name not in method_names:
                            method_names.append(method_name)
        elif test_class_name + ".java" in seq and ":" in seq and "[" in seq and "]" in seq and "," in seq:
                    num = (seq.split("[")[1]).split(",")[0]
                    if num not in line_nums:
                        line_nums.append(num)
    
    for num in line_nums:
        f = open(test_file_path)
        lines = f.readlines()
        line = lines[int(num)-1]
        if line not in res_lines:
            res_lines.append(line)

    # print(line_nums)
    # print(res_lines)
    
    return method_names



#===fix

def get_global_vars(code):
    fields = {}
    trees = javalang.parse.parse(code)
    for _, node in javalang.parse.parse(code):
        func_intervals = set()
        if isinstance(
            node,
            (javalang.tree.FieldDeclaration),
        ):
            stat = get_string(code,node.start_position,node.end_position),
            node_name = node.declarators[0].name,
            # func_intervals.add(
            #     (
            #         node.start_position,
            #         node.end_position,
            #         stat,
            #         node
            #     )
            # )
            # if node.start_position.line >= start_line:
            #     continue
            if node_name not in fields:
                fields[node_name[0]] = stat[0]
    return fields

def remove_comments(code):
    original_code = code
    new_code = code
    try:
        trees = javalang.parse.parse(code)
        if trees.package.documentation:
            package_comments = str(trees.package.documentation)
            new_code = code.replace(package_comments,"")
            code = new_code
    except:
        print("utils.py not found package documentation")

    new_code = code.replace(code.split("package ")[0],"")
    return new_code

def get_package(code):
    try:
        trees = javalang.parse.parse(code)
        if trees.package:
            print("***********package********")
            full_package = "package " + trees.package.name + ";"
            print(full_package)
            return full_package
    except:
        print("package not found")
        return None

def remove_imports(code):
    original_code = code
    new_code = code
    try:
        trees = javalang.parse.parse(code)
        if trees.imports:
            for import_node in trees.imports:
                import_stat = get_string(original_code,import_node.start_position,import_node.end_position)
                new_code = code.replace(import_stat,"")
                code = new_code
    except:
        return new_code
    return new_code

def read_imports(code):
    original_code = code
    imp_list = []
    try:
        trees = javalang.parse.parse(code)
        if trees.imports:
            for import_node in trees.imports:
                import_stat = get_string(original_code,import_node.start_position,import_node.end_position)
                imp_list.append(import_stat)
    except:
        return imp_list
    return imp_list

def get_test_method(test_name,class_content):
    method_list = parse_java_func_intervals(class_content)
    res = {}
    for method_info in method_list:
        start, end, method_name, method_code, node = method_info[0:]
        if test_name == method_name:
            # if node.annotations != None:
            #     for ele in node.annotations:
            #         if ele.name == "Test":
            #             res = [start,end,method_name,method_code,node.annotations]
            # else: # no annotation
            res = {
                'start': start, 'end': end, 'method_name': method_name,
                'method_code': method_code, 'node.annotations': node.annotations
            }
    return res

def get_err_method(test_name,class_content,failure_lines):
    method_list = parse_java_func_intervals(class_content)
    res = None
    for method_info in method_list:
        start, end, method_name, method_code, node = method_info[0:]
        if test_name == method_name:
            for line in failure_lines:
                if int(line) >= start.line and int(line) <= end.line:
                    res = [start,end,method_name,method_code,node.annotations]
    return res

def get_string(data, start, end):
    if start is None:
        return ""

    end_pos = None

    if end is not None:
        end_pos = end.line #- 1

    lines = data.splitlines(True)
    string = "".join(lines[start.line:end_pos])
    string = lines[start.line - 1] + string

    if end is None:
        left = string.count("{")
        right = string.count("}")
        if right - left == 1:
            p = string.rfind("}")
            string = string[:p]

    return string


def parse_java_func_intervals(content: str) -> Set[Tuple[int, int]]:
    func_intervals = set()
    try:
        # trees = javalang.parse.parse(content)
        # print(trees)
        for _, node in javalang.parse.parse(content):
            # print("here")
            if isinstance(
                node,
                (javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration),
            ):
                func_intervals.add(
                    (
                        node.start_position,
                        node.end_position,
                        node.name,
                        get_string(content,node.start_position,node.end_position),
                        node
                    )
                )
        return func_intervals
    except Exception as e: # javalang.parser.JavaSyntaxError
        print("exp", e)
        return func_intervals

def read_java(f):
    fh = open(f, 'r', errors='ignore')
    data = fh.read()
    return data

def clean_code(code):
    code_no_comments = remove_comments(code)
    code_no_imports = remove_imports(code_no_comments)
    return code_no_imports

# trees = javalang.parse.parse(code_no_imports)
# print(trees)

# file = sys.argv[1]
# read_java(file)

def t(response):
    # regex = r"public\s+\w+\s+\w+\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{(?:.|\n)*?\n\s*\}"
    # method_pattern = re.compile(regex, re.DOTALL)
    # matches = method_pattern.findall(code)
    
    # for match in matches:
    #     leftc = match.count("{")
    #     rightc = match.count("}")
    #     print(leftc,rightc)
    #     if leftc == rightc:
    #         print(match)

    code = response.replace("\n"," \n ")
    potential_match_final = ""
    if "//<fix start>" in code:
        potential_match = code.split("//<fix start>")[1]
        potential_match_final = potential_match
        if "//<fix end>" in code:
            potential_match_final = " \n " + potential_match.split("//<fix end>")[0] + " \n "
    if potential_match_final != "":
        import_pattern = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)
        p_imp_matches = import_pattern.findall(code)
        for match in p_imp_matches:
            tmp = "import " + match + ";"
            if tmp in potential_match_final:
                pfinal = potential_match_final.replace(tmp,"")
                potential_match_final = pfinal
        pleft = potential_match_final.count("{")
        pright = potential_match_final.count("}")
        if pleft == pright:
            if "public class " in potential_match_final:
                if "public void" in potential_match_final:
                    tmpstr = potential_match_final.split("public void ")[1]
                    k = tmpstr.rfind("}")
                    new_string = tmpstr[:k] + "\n"
                    final_match = "public void " + new_string
                    if final_match.count("{") == final_match.count("}"):
                        potential_match_final = final_match
                        # print("done")
                elif "void" in potential_match_final:
                    tmpstr = potential_match_final.split("void ")[1]
                    k = tmpstr.rfind("}")
                    new_string = tmpstr[:k] + "\n"
                    final_match = "public void " + new_string
                    if final_match.count("{") == final_match.count("}"):
                        potential_match_final = final_match
    # print(potential_match_final)

def extract_java_code(text):
    lst = text.replace("```java","\n").replace("```","\n").replace("//<fix start>","\n").replace("//<fix end>","\n").split("\n")
    left = 0
    right = 0
    methods = {}
    idx = 0
    method = []
    inAmethod = False
    for line in lst:
        if "public class " in line:
            continue
        idx += 1
        l = line.count("{")
        left += l
        r = line.count("}")
        right += r
        if left == right and right > 0 and inAmethod == True:
            method.append(line)
            left = 0
            right = 0
            methods[str(idx)] = method
            method = []
            inAmethod = False
        elif left > right:
            inAmethod = True
            method.append(line)
        elif line.strip() in ["@Before","@After", "@BeforeEach","@AfterEach","@BeforeAll","@AfterAll","@BeforeClass","@AfterClass"]:
            inAmethod = True
            method.append(line)
    
    dummy_code = "public class Lambda {\n"
    for key in methods:
        method = "\n".join(methods[key]) + "\n"
        dummy_code += method
    dummy_code += "\n}\n"

    method_list = parse_java_func_intervals(dummy_code)
    print(method_list)
    if method_list != None:
        return method_list,True
    else:
        return methods,False

    # for key in methods:
    #     for line in methods[key]:
    #         print(line)
    #     if "()" in methods[key][0] and "{" in methods[key][0]:
    #         potential_method_name = (methods[key][0].split("()"))[0].split(" ")[-1]
    #         print(potential_method_name)
    #         key = potential_method_name