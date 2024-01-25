import csv
import sys
import os
import javalang
import git
import get_uniq_projects
import openai
import datetime
import glob
import utils
import tiktoken
import subprocess
from subprocess import Popen, PIPE
import re
import extract_fixes
import update_pom
import process_line
import sample_tests
from pathlib import Path


run_nondex_cmds = "/home/azureuser/flaky/cmds/run_nondex.sh"
checkout_project_cmds = "/home/azureuser/flaky/cmds/checkout_project.sh"

def generate_input(clone_dir,tests):
    test_list = []
    for tag in tests:
        test_info = {"project":'',"sha":'',"module":'',"file_path":'', \
        "test":'',"type":'',"test_class_content":'',"method_name":'', \
        "status": '',"PR_link":'',"notes":'',"project_url":'',"patch_file":'',
        "patch_file":"","result":[]
        }

        # print(tag)
        project_url = tests[tag]["project"]
        name = tests[tag]["name"]
        sha = tests[tag]["sha"]
        modules =  tests[tag]["module_tests"]
        type = tests[tag]["type"]
        status = tests[tag]["status"]
        pr = tests[tag]["PR_link"]
        notes = tests[tag]["notes"]
        
        for module in modules:
            for test in modules[module]:
                dir_list = []
                if test == None:
                    continue
                class_name = test.split(".")[-2]
                project_dir = os.path.join(clone_dir,sha,name)
                for root, dirs, files in os.walk(project_dir):
                    for file in files:
                        file_path = os.path.join(root,file)
                        test_path = "/".join(test.split(".")[:-1])
                        if file_path.endswith(".java") and file == class_name+".java" \
                            and "/test/" in file_path and test_path in file_path:
                                if file_path not in dir_list:
                                    dir_list.append(file_path)

                file_path_fd = False                    

                for file_path in dir_list:
                    method_name = test.split(".")[-1]
                    if os.path.exists(file_path):
                            with open(file_path,encoding="utf8", errors='ignore') as f:
                                content = f.read()
                                if method_name+"(" in content:
                                    test_info = {"project_url":project_url, "project":name ,"sha":sha ,"module":module ,"file_path":file_path, \
                                                 "status": status,"PR_link":pr,"notes":notes, "patch_file":"","result":[], "patch":"", \
                                    "test":test,"type":type,"test_class_content":content,"method_name":test.split(".")[-1]}
                                    test_list.append(test_info)
                                    file_path_fd = True
                                    continue
                     
                if file_path_fd == False:
                    test_info = {"project_url":project_url,"project":name ,"sha":sha ,"module":module ,"file_path":"", \
                                 "status": status,"PR_link":pr,"notes":notes, "patch_file":"","result":[], "patch":"",\
                                    "test":test,"type":type,"test_class_content":"","method_name":test.split(".")[-1]}
                    
                    print("[ERROR] File Not found:", dir_list, test, flush = True)
                    print(method_name,flush=True)
                    # print(content)
                    
    return test_list

def gpt_fix_err_NOD(test,test_content,err_msg,last_patch,failure_code,updated_helper_res,err_methods):
    for key in updated_helper_res:
        print(updated_helper_res[key])

    test_method = test["method_name"]
    test_type = test["type"].split(";")[0]
    test["gpt_full_response"] = ""
    test["patch"] = ""
    test["patch_file"] = ""
    related_testclass_code = ""
    class_helper_list = []
    for key in updated_helper_res["global_vars"]:
        class_helper_list.append(updated_helper_res["global_vars"][key])

    for key in updated_helper_res:
        if key == "global_vars" or key == "method_names":
            continue
        elif updated_helper_res[key] != None:
            for m in updated_helper_res[key]:
                class_helper_list.append(updated_helper_res[key][m])
    related_testclass_code = "\n".join(class_helper_list) + "\n"

    #test_content
    #test_method,related_testclass_code,err_msg,located_err_lines,method_with_err

    prompt = "To fix the original flaky test {}, the following code is from your previous answer {}, I received errors: {}\n The error is caused by {} in method {}.\n\
    Fix the errors, fix the flaky test, keep the code in the same format:\
    You should think about the solution step by step, print all code between //<fix start> and //<fix end>, but do not print any other text in the response.\n \
    You should follow the rules below for fixing the code:\n \
    - Do not expect me to modify or replace anything in the code.\n \
    - Print all text which is out of code starting with \"//\". \n \
    - Do not add or delete methods.\n \
    - Do not change sugnatures and modifiers of all methods. \n \
    - Fix the flakiness by modifying the provided code. You may make changes to all methods in the class. But do not add code out of methods.\n \
    - Print all code between //<fix start> and //<fix end>.\n \
    - Update dependencies in pom.xml if needed, put the code between <!-- <pom.xml start> --> and <!-- <pom.xml end> -->.  Provide a specific version for the dependency you add. Do not add existing dependencies. Do not include my artifact in your pom.xml code.\n \
    - Your code should be compilable without any errors.\n \
    - Make sure all the arguments are correct.\n \
    - Use compatible types for all variables.\n \
    - Do not define or write helper methods out of the test, make sure all methods you want to call are inside the test method.\n \
    - Update import list if needed, put the code between //<import start> and //<import end>. \n \
    - Assume required classes for original code are setup correctly and do not include them in your code. \n \
        ".format(test_method,related_testclass_code,err_msg,("\t".join(failure_code)).strip(),"\t".join(err_methods))
    
    print(prompt)

    response = openai.ChatCompletion.create(
        model = "gpt-4", #"gpt-3.5-turbo",
        temperature = 0.2,
        messages = [
            {"role": "user", 
            "content":prompt}
        ]
    )
    test["gpt_full_response"] = response["choices"][0]["message"]["content"]
    return test,response,prompt

#helper_res from parse_helper_methods
def locate_err(nondex_output,test_file_path,format_test,helper_res):
    failure_code,failure_lines,method_names = process_line.nod_get_line_location_msg(nondex_output,test_file_path,format_test)
    test_class_content = utils.read_java(test_file_path)
    res_code = {}
    for method_name in method_names:
        res = utils.get_err_method(method_name, test_class_content,failure_lines)
        if res != None:
            method_code = res[3]
            method_name = res[2]
            if method_name not in res_code:
                res_code[method_name]=method_code
        #[start,end,method_name,method_code,node.annotations]
    for res_snip in res_code:
        exist = False
        for key in helper_res:
            if key == "global_vars" or key == "method_names":
                continue
            else:
                for sub_key in helper_res[key]:
                    if res_code[res_snip] == helper_res[key][sub_key]:
                        exist = True
                        break
        if exist == False:
            helper_res["err_method"][res_snip]=res_code[res_snip]
    
    # print(failure_code,failure_lines,method_names,res_code)
    # print(helper_res)

    return failure_code,failure_lines,helper_res,method_names

def parse_helper_methods(test):
    file_path = test["file_path"]
    file = open(file_path, 'r', errors='ignore')
    test_class = file.read()
    test_method_name = test["method_name"]
    res = {"before":{}, "after":{}, "global_vars":{}, "err_method":{},"test_itself":{},"method_names":[]}
    test_itself = utils.get_test_method(test_method_name,test_class)
    res["test_itself"][test_method_name] = test_itself[3]
    before_after_line = utils.get_helper_methods(test_class)
    global_vars = utils.get_global_vars(test_class,before_after_line["earlist_line"])
    if before_after_line["before"] != None:
        res["before"] = before_after_line["before"]
    if before_after_line["after"] != None:
        res["after"] = before_after_line["after"]
    if before_after_line["earlist_line"] != None:
        res["global_vars"] = global_vars
    res["method_names"] = before_after_line["method_names"]
    return res

def gpt_fix_NOD(test,test_content,err_msg,failure_code,updated_helper_res,err_methods):
    for key in updated_helper_res:
        print(updated_helper_res[key])

    test_method = test["method_name"]
    test_type = test["type"].split(";")[0]
    test["gpt_full_response"] = ""
    test["patch"] = ""
    test["patch_file"] = ""
    related_testclass_code = ""
    class_helper_list = []
    for key in updated_helper_res["global_vars"]:
        class_helper_list.append(updated_helper_res["global_vars"][key])

    for key in updated_helper_res:
        if key == "global_vars" or key == "method_names":
            continue
        elif updated_helper_res[key] != None:
            for m in updated_helper_res[key]:
                class_helper_list.append(updated_helper_res[key][m])
    related_testclass_code = "\n".join(class_helper_list) + "\n"

    #test_content
    #test_method,related_testclass_code,err_msg,located_err_lines,method_with_err

    prompt = "You are a software testing expert. I'm going to ask you to fix a flaky test.\n \
    Flaky tests non-deterministically pass or fail due to concurrency, timeout, platform dependency, timezone dependency, etc.\n \
    You should think about the solution step by step, print all code between //<fix start> and //<fix end>, but do not print any other text in the response.\n \
    Problem definition: {} is the flaky test you need to fix, located in the following code of a java class:\n {}\n \
    When the test fails, I get the following error:\n {}\n The error is caused by {} in method {}.\n\
    You should follow the rules below for fixing the code:\n \
    - Do not expect me to modify or replace anything in the code.\n \
    - Print all text which is out of code starting with \"//\". \n \
    - Do not add or delete methods.\n \
    - Do not change sugnatures and modifiers of all methods. \n \
    - Fix the flakiness by modifying the provided code. You may make changes to all methods in the class. But do not add code out of methods. \n \
    - Print all code between //<fix start> and //<fix end>.\n \
    - Update dependencies in pom.xml if needed, put the code between <!-- <pom.xml start> --> and <!-- <pom.xml end> -->.  Provide a specific version for the dependency you add. Do not add existing dependencies. Do not include my artifact in your pom.xml code.\n \
    - Your code should be compilable without any errors.\n \
    - Make sure all the arguments are correct.\n \
    - Use compatible types for all variables.\n \
    - Do not define or write helper methods out of the test, make sure all methods you want to call are inside the test method.\n \
    - Update import list if needed, put the code between //<import start> and //<import end>. \n \
    - Assume required classes for original code are setup correctly and do not include them in your code. \n \
        ".format(test_method,related_testclass_code,err_msg,("\t".join(failure_code)).strip(),"\t".join(err_methods))
    
    print(prompt)

    response = openai.ChatCompletion.create(
        model = "gpt-4", #"gpt-3.5-turbo",
        temperature = 0.2,
        messages = [
            {"role": "user", 
            "content":prompt}
        ]
    )
    test["gpt_full_response"] = response["choices"][0]["message"]["content"]
    return test,response,prompt

def output_nondex(test_type,project,sha,format_test,module,cloneDir,tag,times,file_path):
    output = extract_fixes.verify_by_tool(test_type,project,sha,format_test,module,cloneDir,tag,times)
    msg, res, failure_code = process_nondex_output(output,file_path,format_test)
    return "\n".join(msg), res, failure_code,output

def process_nondex_output(output,file_path,format_test):
    res = ""
    msg = []
    seq_list = output.split("\n")
    if "COMPILATION ERROR" in output:
        res = "COMPILATION ERROR"
        for line in seq_list:
            if "To see the full stack trace of the errors" in line:
                break
            if "ERROR" in line and "Help 1" not in line:
                simp_line = line.replace(file_path,"").replace("\x1b[1;31m","").replace("\x1b[m","").replace("\x1b[1m","").replace("\x1b[36m","").replace("\n", "\t").replace("[ERROR]","").strip()
                if "cannot find symbol" in simp_line:
                    tmp_seq = simp_line.split(" ")[0]
                    if "[" in tmp_seq and "]" in tmp_seq and "," in tmp_seq:
                        simp_line = "cannot find symbol"
                        if simp_line not in msg:
                            msg.append(simp_line)
                if simp_line not in msg:
                    msg.append(simp_line)
        
        return msg,res,None
    else:
        if "test failures" not in output:
            if "BUILD FAILURE" in output:
                return msg,"BUILD FAILURE",None
            
        for pre_line in seq_list:
            line = pre_line.replace("\x1b[1;31m","").replace("\x1b[m","").replace("\x1b[1m","").replace("\x1b[36m","").strip()
            if "cannot find symbol" in line:
                tmp_seq = line.split(" ")[0]
                if "[" in tmp_seq and "]" in tmp_seq and "," in tmp_seq:
                    line = "cannot find symbol"
                    msg.append(line)
            if "There are test failures" in line:
                res = "test failures"
                # msg.append(line)
            if "Failed tests:" in line:
                msg.append(line)
                res = "test failures"
            if "Tests in error:" in line:
                indx = seq_list.index(pre_line)
                msg.append(seq_list[indx+1])
                res = "test failures"

        s_list = output.split("<<< FAILURE!")[1:]
        for item in s_list:
            if "Results" in item and "Failures: 1" in item:
                add_info = item.split("Results")[0]
                if "at" in add_info:
                    err_info = add_info.split("\tat")[0]
                    if err_info not in msg:
                        msg.append(err_info.replace("\n","\t"))
            #Errors: 1
            if "Results" in item and "Errors: 1" in item:
                add_info = item.split("Results")[0]
                if "at" in add_info:
                    err_info = add_info.split("\tat")[0]
                    if err_info not in msg:
                        msg.append(err_info.replace("\n","\t"))
        if len(msg) == 0:
            for pre_line in seq_list:
                line = pre_line.replace("\x1b[1;31m","").replace("\x1b[m","").replace("\x1b[1m","").replace("\x1b[36m","")
                if "ERROR" in line and "Help 1" not in line and "Time elapsed:" not in line \
                    and "For more information about the errors and possible solutions" not in line:
                    line.replace(file_path,"")
                    msg.append(line)
        failure_code,failure_lines = process_line.get_line_location_msg(output,file_path,format_test)
        if len(msg) > 0:
            uniq_msg = []
            testname = format_test.replace("#",".")
            classname = format_test.split("#")[0]
            for m in msg:
                new_m = m.replace(testname,"").replace(classname,"").replace("[ERROR]","").replace("ERROR!","").replace("ERROR!","")
                update_m = new_m
                if "Time elapsed:" in new_m:
                    timesec = (new_m.split("Time elapsed:")[1]).split("sec")[0]
                    update_m = new_m.replace(timesec,"").replace("Time elapsed:","").replace(" sec ","")
                if update_m.strip() not in uniq_msg:
                    uniq_msg.append(update_m.strip())
            return uniq_msg,res,failure_code
        else:
            if "ERROR" in output:
                return msg,"BUILD FAILURE",None
            else:
                return msg,"test pass",None

def simply_parse(gpt_full_response):
    simple_patch = {"code":"", "import":[], "pom":""}
    code = gpt_full_response["choices"][0]["message"]["content"]
    import_pattern = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)
    imp_matches = import_pattern.findall(code)
    for match in imp_matches:
        imp = "import " + match + ";"
        if imp not in simple_patch["import"]:
            simple_patch["import"].append(imp)
    potential_match_final = ""
    if "<!-- <pom.xml start> -->" in code and "<!-- <pom.xml end> -->" in code:
        pom_stat = (code.split("<!-- <pom.xml start> -->")[1]).split("<!-- <pom.xml end> -->")[0]
        simple_patch["pom"] = pom_stat
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
    simple_patch["code"] = potential_match_final
    return simple_patch


def apply_before_processing(project,sha,module,test_fullname,test_type,method_name,simple_patch,file_path,cloneDir,tag,times):
    final_class = apply_patch(project,sha,module,test_fullname,test_type,method_name,simple_patch,file_path,cloneDir)
    print(("[Simple patch start] Running test with simple patch {} with type {} from project {} sha {} module {} \
                    ").format(test_fullname, test_type, project, sha, module),flush = True)
    if final_class != None:
        format_test = extract_fixes.replace_last(test_fullname, '.', '#')
        msg, res, failure_code,ndx_output = output_nondex(test_type,project,sha,format_test,module,cloneDir,tag,times,file_path)
    else:
        print("error when applying simple patch without processing")
    print(("[Simple patch end] Running test with simple patch {} with type {} from project {} sha {} module {}, simple result: {} \
                    ").format(test_fullname, test_type, project, sha, module,res),flush = True)
    extract_fixes.git_stash(project, sha, cloneDir,file_path)
    return res

def parse_patch(gpt_full_response,file_path,test_name,time):
    file = open(file_path, 'r', errors='ignore')
    test_class = file.read()

    patch = {"code":{"fields":{}, "methods":{}}, "import":[], "pom":"", "toreplace":{"field_names":[], "method_names":[]}}
    response = gpt_full_response.replace("```java","").replace("```","")
    print(time, test_name, "process response =======================\n",flush=True)
    print(response,flush=True)
    print(time, test_name,"process response =======================\n",flush=True)
    potential_match_final = response

    response_noimp = potential_match_final
    static_import_pattern = re.compile(r"import\s+(static\s+)?([\w\.]+(\.\*)?);", re.MULTILINE)
    static_imp_matches = static_import_pattern.findall(potential_match_final)
    orig_imp_matches = static_import_pattern.findall(test_class)
    orig_imps = []
    for orig_match in orig_imp_matches:
        imp_stat = ""
        if orig_match[0].strip() == "static" and orig_match[1] != '':
            imp_stat = "import static " + orig_match[1] + ";"
        elif orig_match[0].strip() == "" and orig_match[1] != '':
            imp_stat = "import " + orig_match[1] + ";"
        orig_imps.append(imp_stat)
    orig_imps_str = "\n".join(orig_imps)
        
    for imp_match in static_imp_matches:
        if imp_match[0].strip() == "static" and imp_match[1] != '':
            imp_stat = "import static " + imp_match[1] + ";"
        elif imp_match[0].strip() == "" and imp_match[1] != '':
            imp_stat = "import " + imp_match[1] + ";"
        simp_name = imp_stat.split(".")[-1]
        response_noimp = potential_match_final.replace(imp_stat,"")
        potential_match_final = response_noimp
        if imp_stat not in test_class and "." + simp_name not in orig_imps_str:
            print("will add ",imp_stat,flush=True)
            patch["import"].append(imp_stat.replace("\n","").replace(";","")+";\n ")
        else:
            print("not add", imp_stat)
    
    try:
        dummy_code = "public class Lambda {\n" + response_noimp + "\n}\n"
        trees = javalang.parse.parse(dummy_code)
    except:
        try:
            code = response_noimp
            potential_match_final2 = code
            if "//<fix start>" in code:
                potential_match = code.split("//<fix start>")[1]
                potential_match_final2 = potential_match
                if "//<fix end>" in code:
                    potential_match_final2 = " \n " + potential_match.split("//<fix end>")[0] + " \n "
            elif "<fix start>" in code:
                potential_match = code.split("<fix start>",1)[1]
                potential_match_final2 = potential_match
                if "<fix end>" in code:
                    potential_match_final2 = " \n " + potential_match.rsplit("<fix end>",1)[0] + " \n "
            response_noimp2 = potential_match_final2
            dummy_code = "public class Lambda {\n" + response_noimp2 + "\n}\n"
            trees = javalang.parse.parse(dummy_code)
        except:
            try:
                code = response_noimp
                response_noimp3 = code
                if "public class " not in code:
                    potential_match3 = code.split('public ', 1)[1]
                    potential_match_final3 = potential_match3.rsplit("}",1)[0]
                    response_noimp3 = 'public ' + potential_match_final3 + "\n}\n"
                else:
                    potential_match3 = code.split('{', 1)[1]
                    potential_match_final3 = potential_match3.rsplit("}",2)[0]
                    response_noimp3 = potential_match_final3 + "\n}\n"

                dummy_code = "public class Lambda {\n" + response_noimp3 + "\n}\n"
                trees = javalang.parse.parse(dummy_code)
            except:
                print(dummy_code)
                # exit(0)
                return None

    func_intervals = set()
    fields = set()
    for _, node in trees:
        if isinstance(node,(javalang.tree.FieldDeclaration),):
            fields.add(
                (
                    node.start_position,
                    node.end_position,
                    utils.get_string(dummy_code,node.start_position,node.end_position),
                    node.declarators[0].name,
                    node
                )
            )
        elif isinstance(node,(javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration),):
            func_intervals.add(
                (
                    node.start_position,
                    node.end_position,
                    node.name,
                    utils.get_string(dummy_code,node.start_position,node.end_position),
                    node
                )
            )
            # print(utils.get_string(dummy_code,node.start_position,node.end_position))
        
    for field in fields:
        if field[2] not in test_class:
            patch["code"]["fields"][field[3]] = field[2]
            patch["toreplace"]["field_names"].append(field[3])

    for method in func_intervals:
        patch["toreplace"]["method_names"].append(method[2])
        patch["code"]["methods"][method[2]] = method[3]

    if "<!-- <pom.xml start> -->" in response and "<!-- <pom.xml end> -->" in response:
        pom_stat = (response.split("<!-- <pom.xml start> -->")[1]).split("<!-- <pom.xml end> -->")[0]
        patch["pom"] = pom_stat

    print(time, test_name, "parsed patch=======================\n",flush=True)
    print(patch,flush=True)
    print(time, test_name,"parsed patch=======================\n",flush=True)

    return patch

def apply_patch(project,sha,module,test_fullname,test_type,method_name,patch,file_path,cloneDir,updated_helper_res):
    # print(patch)
    # print(updated_helper_res)
    format_test = extract_fixes.replace_last(test_fullname, '.', '#')
    if patch == None:
        print("[ERROR]No Patch",flush = True)
        return None
    try:
        file = open(file_path, 'r', errors='ignore')
        class_content = file.read()
        fixed_class = class_content
        for f_method in patch["code"]["methods"]:
            for key in updated_helper_res:
                if key == "method_names" or key == "global_vars":
                    continue
                else:
                    if f_method in updated_helper_res[key]:
                        old_method = updated_helper_res[key][f_method]
                        new_method = patch["code"]["methods"][f_method]
                        fixed_class = class_content.replace(old_method,new_method)
                        class_content = fixed_class
                        # print(old_method)
                        # print("newwwwww method")
                        # print(new_method)
                        print(f_method, "changed to:\n", new_method)
        for var in patch["code"]["fields"]:
            for key in updated_helper_res["global_vars"]:
                if var == key:
                    old_var = updated_helper_res["global_vars"][key]
                    new_var = patch["code"]["fields"][var]
                    fixed_class = class_content.replace(old_var,new_var)
                    class_content = fixed_class
        
        if len(patch["import"]) > 0:
            package = utils.get_package(class_content)
            if package != None:
                seq = fixed_class.split(package)
                final_class = seq[0] + "\n" + package + "\n" + "\n".join(patch["import"]) + "\n" + seq[1]
            else:
                seq = fixed_class.split("public class ")
                final_class = seq[0] + "\n".join(patch["import"]) + "\n" + "public class " + seq[1]
        else:
            final_class = fixed_class

        print(("[Applying FIX] Applying patch on test {}").format(format_test),flush = True)
        f = open(file_path, "w", errors='ignore')
        f.write(final_class)
        f.close()

        if patch["pom"] != "":
            print("pom need to update")
            dep2add = patch["pom"]
            deps = dep2add
            if "<dependencies>" in patch["pom"]:
                dep2add  = patch["pom"].replace("<dependencies>","")
            if "</dependencies>" in dep2add:
                deps = dep2add.replace("</dependencies>","")
            if "/src/" in file_path:
                root_path = file_path.split("/src/")[0]
                pom_path = os.path.join(root_path,"pom.xml")
                if os.path.exists(pom_path):
                    extract_fixes.git_stash(project, sha, cloneDir,pom_path)
                    update_pom.add_dependency(pom_path,deps)
                    print("pom updated")
        return final_class
    except:
        return None


def ask_gpt(test_list,save_resfile,cloneDir,save_dir,final_resfile):
    encoding = tiktoken.encoding_for_model("gpt-4")
    fields = ["project_url","project","sha","module", "test","type", \
              "status", "PR_link","notes",
              "patch","method_name", \
                "gpt_full_response","file_path","gpt_prompt","is_patched","test_class_content","patch_file","result"]
    index = 0
    print("Len:", len(test_list),flush=True)
    # print(test_list)
    com_err = []
    test_failure = []
    unfixed_test = test_list.copy() #initial unfixed_test includes all tests

    with open(save_resfile, 'w', newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for test in test_list:
            index += 1
            print("start to run:", test["test"],test_list.index(test))
            original_test = test.copy()
            done = False
            patch_is_none = False
            ans_chain = {}
            time = 0
            identical_err = 0
            try:
            # if True:
                print(("[Before fix] Running test {} with type {} from project {} sha {} module {} \
                    ").format(test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)
                extract_fixes.git_stash(test["project"], test["sha"], cloneDir,test["file_path"])
                extract_fixes.restore_project(test["project"], test["sha"], cloneDir)
                format_test = extract_fixes.replace_last(test["test"], '.', '#')
                msg, res, original_failure_code,ndx_output = output_nondex(test["type"],test["project"],test["sha"],format_test,test["module"],cloneDir,"BeforeFix","1",test["file_path"])
                print("time:", time,test["test"], msg, res,flush=True)
                res_str = str(time) + ":" + res
                test["result"].append(res_str)
                helper_res = parse_helper_methods(test)
                failure_code,failure_lines,updated_helper_res,err_methods = locate_err(ndx_output,test["file_path"],format_test,helper_res)
                # print(failure_code,failure_lines,updated_helper_res,err_methods)
                # 0 - before fix
                if time not in ans_chain:
                    ans_chain[time] = [msg,res]
                if res == "COMPILATION ERROR" or res == "BUILD FAILURE":
                    print("original test not compilable, or build failure, or incorrect test name")
                    done = True
                    print(("[original test not compilable] time {} Fix test {} with type {} from project {} sha {} module {} \
                                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)  
                    test["result"].append("original test not compilable, or build failure, or incorrect test name")
                    write_final_info(test,final_resfile)
                    unfixed_test.remove(test)
                    continue
                if res == "test pass":
                    print("original test not flaky")
                    print(("[original test not flaky] time {} Fix test {} with type {} from project {} sha {} module {} \
                                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)  
                    done = True
                    test["result"].append("original test not flaky")
                    write_final_info(test,final_resfile)
                    unfixed_test.remove(test)
                    continue
                last_msg = msg
                
                if test["type"] == "ID" or test["type"] == "NOD":
                    # 1 - first fix
                    time += 1
                    if time not in ans_chain:
                        ans_chain[time] = []
                        test,response,prompt,patch = generate_NOD_patch(test,index,writer,None,last_msg,None,time,failure_code,updated_helper_res,err_methods)
                        print(prompt,response,flush=True)
                        if patch != None: # apply fix, run nondex
                            final_class = apply_patch(test["project"],test["sha"],test["module"],test["test"],test["type"],test["method_name"],patch,test["file_path"],cloneDir,updated_helper_res)
                            print(("[After fix] time {} Running test {} with type {} from project {} sha {} module {} \
                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)
                            # print("************************fixed class\n",final_class,"************************fixed class\n")
                            msg, res, failure_code,ndx_output = output_nondex(test["type"],test["project"],test["sha"],format_test,test["module"],cloneDir,"AfterFix","1",test["file_path"])
                            helper_res = parse_helper_methods(test)
                            failure_code,failure_lines,updated_helper_res,err_methods = locate_err(ndx_output,test["file_path"],format_test,helper_res)
                            ans_chain[time] = [msg,res]
                            print("time:", time, msg, res,flush=True)
                            # exit(0)
                            last_msg = msg
                            last_patch = patch["code"]
                            first_patch = patch["code"]
                            res_str = str(time) + ":" + res
                            test["result"].append(res_str)
                            if res == "test pass":
                                print(("[****GOOD FIX*****] time {} Fix test {} with type {} from project {} sha {} module {} \
                                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)  
                                patch_file = write_patch(save_dir,test["test"],test["project"],test["sha"],test["module"],patch,time)
                                test["patch_file"] = patch_file
                                test["result"].append("summary:good fix")
                                write_final_info(test,final_resfile)
                                for time in ans_chain:
                                    print("SUMMARY",index,time,test["test"], test["type"], test["project"], test["sha"], test["module"], ans_chain[time],flush=True)
                                done = True
                                unfixed_test.remove(test)
                                continue
                            else:
                                if res == "BUILD FAILURE":
                                    extract_fixes.restore_project(test["project"], test["sha"], cloneDir)
                                # more try with feedback
                                for time in range(2, 6):
                                    if time not in ans_chain:
                                        ans_chain[time] = []
                                        test,response,prompt,patch = generate_NOD_patch(test,index,writer,last_msg,None,last_patch,time,failure_code,updated_helper_res,err_methods)
                                        print(prompt,response,flush=True)
                                        if patch != None: # apply fix, run nondex
                                            final_class = apply_patch(test["project"],test["sha"],test["module"],test["test"],test["type"],test["method_name"],patch,test["file_path"],cloneDir,updated_helper_res)
                                            print(("[After fix] time {} Running test {} with type {} from project {} sha {} module {} \
                                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)
                                            # print("************************fixed class\n",final_class,"************************fixed class\n")

                                            msg, res, new_failure_code,ndx_output = output_nondex(test["type"],test["project"],test["sha"],format_test,test["module"],cloneDir,"AfterFix","1",test["file_path"])
                                            helper_res = parse_helper_methods(test)
                                            new_failure_code,failure_lines,updated_helper_res,err_methods = locate_err(ndx_output,test["file_path"],format_test,helper_res)
                                            print("time:", time, msg, res,flush=True)
                                            ans_chain[time]=[msg,res]
                                            res_str = str(time) + ":" + res
                                            test["result"].append(res_str)
                                            if res == "test pass": 
                                                done = True
                                                print(("[****GOOD FIX*****] time {} Fix test {} with type {} from project {} sha {} module {} \
                                        ").format(time, test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True) 
                                                patch_file = write_patch(save_dir,test["test"],test["project"],test["sha"],test["module"],patch,time)
                                                test["patch_file"] = patch_file
                                                test["result"].append("summary:good fix")
                                                write_final_info(test,final_resfile)
                                                for time in ans_chain:
                                                    print("SUMMARY",index,time,test["test"], test["type"], test["project"], test["sha"], test["module"], ans_chain[time],flush=True)
                                                unfixed_test.remove(test)
                                                break
                                            else: 
                                                if res == "BUILD FAILURE":
                                                    extract_fixes.restore_project(test["project"], test["sha"], cloneDir)
                                                if last_msg == msg:
                                                    identical_err += 1
                                                last_msg = msg
                                                failure_code = new_failure_code
                                                if patch["code"] != "":
                                                    last_patch = patch["code"]
                                                else:
                                                    last_patch = first_patch
                                        else:
                                            print(time, "patch is none, reuse patch from last time",flush=True)
                                            break
                                            
                        else:
                            if test == None:
                                print("original test code not found",test)
                                done = True
                                unfixed_test.remove(original_test)
                                original_test["result"].append("original test code extraction error")
                                write_final_info(original_test,final_resfile)
                            else:
                                print("1st patch parsed with error",patch,flush=True)
                                patch_is_none = True
                                done = True
                                test["result"].append("1st patch is none")
                                write_final_info(test,final_resfile)
                            continue
               
            except Exception as e: #openai.error.InvalidRequestError
            # if True:
                print("********** START #{}".format(index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
                print("ERROR", e,flush = True)
                print("*EXCEPTION*")
                print(("[****BAD FIXES ***_other_exception_**] Fix test {} with type {} from project {} sha {} module {} \
                    ").format(test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)  
                test["result"].append(e)
                unfixed_test.remove(test)
                done = True
                write_final_info(test,final_resfile)
                print("*********** END #{}".format(index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
            
            if done == False:            
                categary = []
                for time in ans_chain:
                    print("SUMMARY",index,time,test["test"], test["type"], test["project"], test["sha"], test["module"], ans_chain[time],flush=True)
                    if time != 0:
                        if len(ans_chain[time]) >= 2:
                            categary.append(ans_chain[time][1])

                if "test failures" in categary:
                    test["result"].append("summary:test_failures")
                    write_final_info(test,final_resfile)
                    test_failure.append(test)
                    print("*TESTFAIL*")
                    print(("[****BAD FIXES ***_test_fail_**] Fix test {} with type {} from project {} sha {} module {} \
                        ").format(test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)  
                else:
                    if "COMPILATION ERROR" in categary:
                        test["result"].append("summary:compilation_error")
                        write_final_info(test,final_resfile)
                        com_err.append(test)
                        print("*COMPERR*")
                        print(("[****BAD FIXES ***_compilation_error_**] Fix test {} with type {} from project {} sha {} module {} \
                            ").format(test["test"], test["type"], test["project"], test["sha"], test["module"]),flush = True)
    print("=========compile error:", len(com_err), "\n", "===============test failures", len(test_failure))
    return unfixed_test

        
def generate_NOD_patch(test,index,writer,err_msg,orig_nondex_msg,last_patch,time,failure_code,updated_helper_res,err_methods):
    test_class = test["test_class_content"]
    test_content = extract_test_method(test["method_name"], test["test_class_content"])
    if test_content == None:
        # print(test)
        # print("original error here",test, flush=True)
        print("********** START #{}".format(index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
        print("ERROR when extracting test method", flush = True)
        print("*********** END #{}".format(index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
        return None,None,None,None
    print("********** time {} ASK GPT START #{}".format(time, index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
    if err_msg == None and last_patch == None:
        test,response,prompt = gpt_fix_NOD(test,test_content,orig_nondex_msg,failure_code,updated_helper_res,err_methods)
    if orig_nondex_msg == None:
        test,response,prompt = gpt_fix_err_NOD(test,test_content,err_msg,last_patch,failure_code,updated_helper_res,err_methods)
    if test != None :
        patch = parse_patch(test["gpt_full_response"],test["file_path"],test["method_name"],time)
        if patch != None:
            test["is_patched"] = True
        else:
            test["is_patched"] = False
            print("no patch here, or patch failed to parse")
            return test,response,prompt,None
        test["gpt_prompt"] = prompt
        test["patch"] = patch
        info = test.copy()
        info["test_class_content"] = time # record time in test_class_content
        writer.writerow(info)
    print("********** time {} GPT ANSWER END #{}".format(time, index), datetime.datetime.now(), test["project"], test["module"], test["method_name"], "*************************************",flush = True)
    test["patch"] = patch
    return test,response,prompt,patch 

def write_item(item_dict, save_resfile):

    fields = ["project","sha","module","file_path", \
        "test","type","method_name", \
        "gpt_full_response", "patch","gpt_prompt","status","PR_link","notes","patch_file"]

    with open(save_resfile, 'w', newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        # for row in item_dict:
        #     writer.writerow(row)

def write_patch(dir,test,project,sha,module,patch,time):
    patch_dir = os.path.join(dir,project,sha,module,test)
    Path(patch_dir).mkdir(parents=True, exist_ok=True)
    patch_file = os.path.join(patch_dir,str(time)+".java")
    file = open(patch_file, 'w')
    file.write(str(patch))
    file.close()
    return patch_file

def write_final_info(test,final_resfile):
    info = test.copy()
    for key in ["test_class_content", "method_name","project", "patch","gpt_prompt","gpt_full_response"]:
        if key in info:
            info.pop(key)
    fields = ["project_url","sha","module", "test","type", \
        "status", "PR_link","notes",\
        "file_path","is_patched","patch_file","result"]
    with open(final_resfile, 'a', newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writerow(info)

def extract_test_method(test_name, class_content):
    res = utils.get_test_method(test_name, class_content)
    if res == None:
        return None
    test_method = res[3]
    return test_method

if __name__ == "__main__":
    args = sys.argv[1:]
    pr_csv = args[0]
    clone_dir = args[1]
    api_key = args[2]
    save_resfile = args[3]
    final_resfile = args[4]
    save_dir = args[5]
    unfixed_csv = args[6]

    openai.api_key = api_key
    openai.organization = os.getenv("OPENAI_ORGANIZATION")
    tests = get_uniq_projects.collect_tests(pr_csv)
    test_list = generate_input(clone_dir, tests)
    unfixed_test = ask_gpt(test_list,save_resfile,clone_dir,save_dir,final_resfile)
    sample_tests.filter_tests(unfixed_test,unfixed_csv)
    for item in unfixed_test:
        print("unfixed: ", item)