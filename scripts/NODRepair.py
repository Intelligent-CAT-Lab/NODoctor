import argparse
import csv
import os
import sys
from utils import read_csv, get_test_files, locate_test_code, \
    get_realted_helper, get_global_vars, \
        extract_nondex_failure

def process_single_entry(entry, clone_dir):
    test_full_name = entry['Fully-Qualified Test Name (packageName.ClassName.methodName)']
    project_url = entry['Project URL']
    repo_name = project_url.split('/')[-1]
    sha = entry['SHA Detected']
    module = entry['Module Path']
    
    potential_test_files = []
    potential_test_files = get_test_files(test_full_name, clone_dir, repo_name, sha, module)
    if len(potential_test_files) == 0:
        return 'Failure to localize test file!'
    if len(potential_test_files) > 1:
        return 'Ambitious test file localization!'
    
    localization_info = {}
    localization_info = get_test_code(potential_test_files[0], test_full_name)
    
    helper_methods = get_realted_helper(potential_test_files[0])
    localization_info.update(helper_methods)
    localization_info.update({'repo_name': repo_name})
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
        
# def prompt_model()
        
def repair_single_entry(entry, clone_dir, iter = 5):
    """entry(['Project URL', 'SHA Detected', 'Module Path', 
    'Fully-Qualified Test Name (packageName.ClassName.methodName)', 'Category', 
    'Status', 'PR Link', 'Notes', None, 'start', 'end', 'method_name', 'method_code',
    'node.annotations', 'before', 'after', 'earlist_line', 'helper_method_names'])"""
    # initial run check with nondex 
    extract_nondex_failure(entry, clone_dir)
    
    
    # prompt
    
    
    # restore repo code
    



def main(args):
    input_csv, clone_dir, api_key, output_dir = args.input_csv, args.clone_dir, args.api_key, args.output_dir
    entries = process_input_csv(input_csv, clone_dir)
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", help="Input csv file including repo,sha,test", required=True)
    parser.add_argument("--clone_dir", help="Location of cloned projects", required=True)
    parser.add_argument("--api_key", help="Your OPENAI key", required=True)
    parser.add_argument("--output_dir", help="Output directory", required=True)
    args = parser.parse_args()
    main(args)