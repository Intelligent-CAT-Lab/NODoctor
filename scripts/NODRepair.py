import argparse
import csv
import os
import sys
import openai
from openai import OpenAI
from utils import read_csv, get_test_files, locate_test_code, \
    get_realted_helper, get_global_vars, \
        extract_nondex_result, get_err_method_names, parse_patch, apply_patch, read_java

def process_single_entry(entry, clone_dir):
    test_full_name = entry['Fully-Qualified Test Name (packageName.ClassName.methodName)']
    project_url = entry['Project URL']
    repo_name = project_url.split('/')[-1]
    sha = entry['SHA Detected']
    module = entry['Module Path']
    
    repo_path = os.path.join(clone_dir, sha, repo_name)
    
    potential_test_files = []
    potential_test_files = get_test_files(test_full_name, clone_dir, repo_name, sha, module)
    if len(potential_test_files) == 0:
        return 'Failure to localize test file!'
    if len(potential_test_files) > 1:
        return 'Ambitious test file localization!'
    
    original_test_class_content = read_java(potential_test_files[0])
    entry.update({'original_test_class_content':original_test_class_content, 'repo_path': repo_path})
    
    localization_info = {}
    localization_info = get_test_code(potential_test_files[0], test_full_name)
    
    helper_methods, global_vars = get_realted_helper(potential_test_files[0])
    localization_info.update(helper_methods)
    localization_info.update({'repo_name': repo_name, 'test_file_path': potential_test_files[0], 'global_vars': global_vars})
    return localization_info
    
    
def get_test_code(potential_test_file, test_full_name):
    """
    {'start': Position(line=, column=), 'end': Position(line=, column=), 
    'method_name':, 'method_code': , 
    'node.annotations': [Annotation(element=None, name=Test)]}
    """
    localization_info = {}
    localization_info = locate_test_code(potential_test_file, test_full_name)
    return localization_info

def process_input_csv(input_csv, clone_dir):
    entries = read_csv(input_csv)
    for entry in entries:
        single_entry_addinfo = process_single_entry(entry, clone_dir)
        entry.update(single_entry_addinfo)
        
        repair_single_entry(entry, clone_dir)
        
        print(entry.keys())
        exit(0)

def get_model_response(entry, initial = False):
    test_method_code = entry['method_code']
    test_method_name = entry['method_name']
    globals_code = '\n'.join(entry['global_vars'].values())
    err_class_code = f"{entry['before']}\n{entry['after']}\n{globals_code}\n{test_method_code}"
    
    if initial:
        err_msg = entry['initial_err_msg']
        err_code = entry['initial_err_code']
        err_method_names = entry['initial_err_method_names']
    else:
        print('here')
        exit(0)
    
    prompt = f"You are a software testing expert. I'm going to ask you to fix a flaky test.\n \
    Flaky tests non-deterministically pass or fail due to concurrency, timeout, platform dependency, timezone dependency, etc.\n \
    You should think about the solution step by step, print all code between //<fix start> and //<fix end>, but do not print any other text in the response.\n \
    Problem definition: {test_method_name} is the flaky test you need to fix, located in the following code of a java class:\n {err_class_code}\n \
    When the test fails, I get the following error:\n {err_msg}\n The error is caused by '{err_code}' in method {err_method_names}.\n\
    You should follow the rules below for fixing the code:\n \
    - Do not expect me to modify or replace anything in the code.\n \
    - Print all text which is out of code starting with \"//\". \n \
    - Do not delete methods.\n \
    - Do not change signatures and modifiers of all methods. \n \
    - Fix the flakiness by modifying the provided code. You may make changes to all methods in the class. But do not add code out of methods. \n \
    - Print all code between //<fix start> and //<fix end>.\n \
    - Update dependencies in pom.xml if needed, put the code between <!-- <pom.xml start> --> and <!-- <pom.xml end> -->.  Provide a specific version for the dependency you add. Do not add existing dependencies. Do not include my artifact in your pom.xml code.\n \
    - Your code should be compilable without any errors.\n \
    - Make sure all the arguments are correct.\n \
    - Use compatible types for all variables.\n \
    - Do not define or write helper methods out of the test, make sure all methods you want to call are inside the test method.\n \
    - Update import list if needed, put the code between //<import start> and //<import end>. \n \
    - Assume required classes for original code are setup correctly and do not include them in your code. \n "
    
    print(prompt)
    response = prompt_model(prompt)
    print(response)
    return prompt, response
        
def prompt_model(prompt, model_name='gpt-4o-mini'):
    try:
        model = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
        )
        outputs = model.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Python programmer and assistant"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        response = outputs.choices[0].message.content
    except Exception as e:
        print(e)
        response = f'{e}'
    return response
        
def repair_single_entry(entry, clone_dir, iter = 5):
    """entry(['Project URL', 'SHA Detected', 'Module Path', 
    'Fully-Qualified Test Name (packageName.ClassName.methodName)', 'Category', 
    'Status', 'PR Link', 'Notes', None, 'start', 'end', 'method_name', 'method_code',
    'node.annotations', 'before', 'after', 'earlist_line',
    'helper_method_names', 'repo_name','test_file_path', 'global_vars'])"""
    # initial run check with nondex 
    print(f"* Process single entry...")
    initial_summary, initial_err_msg, initial_err_code, initial_err_method_names = extract_nondex_result(entry, clone_dir)
    if initial_summary == "PASS":
        entry.update({'repair_result': 'Initial run with no failures!'})
    elif initial_summary == 'FAILURE':
        # print(initial_summary, initial_err_msg, initial_err_code)
        entry.update({
            'initial_summary': initial_summary,
            'initial_err_msg': initial_err_msg,
            'initial_err_code': initial_err_code,
            'initial_err_method_names': initial_err_method_names
        })
        print(entry.keys())
        prompt, response = get_model_response(entry, initial = True)
        patch = parse_patch(response, entry)
        apply_patch(entry, patch)
    
    
    # prompt
    
    
    # restore repo code
    



def main(args):
    input_csv, clone_dir, output_dir = args.input_csv, args.clone_dir, args.output_dir
    entries = process_input_csv(input_csv, clone_dir)
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", help="Input csv file including repo,sha,test", required=True)
    parser.add_argument("--clone_dir", help="Location of cloned projects", required=True)
    parser.add_argument("--output_dir", help="Output directory", required=True)
    args = parser.parse_args()
    main(args)