【Fixing Issues Now】

# NODoctor
The artifact repository for paper *"Can ChatGPT repair Non-Order-Dependent Tests?"* in Flaky Test Workshop at ICSE2024, Lisbon, Portugal, April 2024.

## Reproduce results

1. To set up the environments:
```
bash -x scripts/setup.sh
export OPENAI_API_KEY=${Your OPENAI_API_KEY}
```
You’ll also need to install the following:
```
- Java 8 and 11
- Maven 3.9.6 (Earlier versions of NODoctor were working with Maven 3.6.3, which is now outdated.)
```

2. To clone all Java projects into a directory, one can run the following command:
```
bash -x scripts/clone.sh [InputCSV] [CloneDIR]
```
The arguments are as follows:
- `InputCSV`: An input csv files which includes the info of `Project URL,SHA Detected,Module Path`, such as:
```
https://github.com/apache/nifi,2bd752d868a8f3e36113b078bb576cf054e945e8,nifi-commons/nifi-record
https://github.com/alibaba/fastjson,93d8c01e907fe35a8ff0eb5fe1c3b279d2f30282,.,

```
- `CloneDIR`: the directory where all Java projects to be cloned

After cloning done, you can install all the projects:   
```
bash -x scripts/install.sh [InputCSV] [CloneDIR]
```

3. To reproduce the results, one can run the following command:
```
bash -x scripts/repair.sh [InputCSV] [CloneDIR] [ResultDir]
```
The arguments are as follows:
- `InputCSV`: An input csv files which includes the info of `Project URL,SHA Detected,Module Path,Fully-Qualified Test Name (packageName.ClassName.methodName),Category,Status,PR Link,Notes` for each test (same information as in [IDoFT](https://github.com/TestingResearchIllinois/idoft), such as:
```
Project URL,SHA Detected,Module Path,Fully-Qualified Test Name (packageName.ClassName.methodName),Category,Status,PR Link,Notes
https://github.com/apache/nifi,2bd752d868a8f3e36113b078bb576cf054e945e8,nifi-commons/nifi-record,org.apache.nifi.serialization.record.TestDataTypeUtils.testInferTypeWithMapNonStringKeys,ID,,,,
https://github.com/alibaba/fastjson,93d8c01e907fe35a8ff0eb5fe1c3b279d2f30282,.,com.alibaba.json.bvt.GroovyTest.test_groovy,NOD,RepoArchived,,
```
- `CloneDIR`: the directory where all Java projects are located
- `ResultDir`: the directory to save all results. Each run of the experiments will generate a directory with a unique SHA as the folder name, under the folder there are patches, detailed result information, and all logs
