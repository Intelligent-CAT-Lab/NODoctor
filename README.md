【Fixing Issues Now】

# NODoctor
The artifact repository for paper *"Can ChatGPT repair Non-Order-Dependent Tests?"* in Flaky Test Workshop at ICSE2024, Lisbon, Portugal, April 2024.

## Reproduce results

1. To set up the environments:
```
bash -x scripts/setup.sh
```
2. To clone all Java projects into a directory, one can run the following command:
```
bash -x clone.sh [InputCSV] [CloneDIR]
```
The arguments are as follows:
- `InputCSV`: An input csv files which includes the info of `project,sha,module`, such as:
```
https://github.com/apache/nifi,2bd752d868a8f3e36113b078bb576cf054e945e8,nifi-commons/nifi-record
```
- `CloneDIR`: the directory where all Java projects to be cloned

3. To reproduce the results, one can run the following command:
```
bash -x scripts/repair.sh [InputCSV] [CloneDIR] [APIKey] [ResultDir] NOD_repair.py
```
The arguments are as follows:
- `InputCSV`: An input csv files which includes the info of `project,sha,module,test,type,status,pr,notes` for each test (same information as in [IDoFT](https://github.com/TestingResearchIllinois/idoft), such as:
```
https://github.com/apache/nifi,2bd752d868a8f3e36113b078bb576cf054e945e8,nifi-commons/nifi-record,org.apache.nifi.serialization.record.TestDataTypeUtils.testInferTypeWithMapNonStringKeys,ID,,,,
```
- `CloneDIR`: the directory where all Java projects are located
- `APIKey`: OpenAI token
- `ResultDir`: the directory to save all results. Each run of the experiments will generate a directory with a unique SHA as the folder name, under the folder there are patches, detailed result information, and all logs
