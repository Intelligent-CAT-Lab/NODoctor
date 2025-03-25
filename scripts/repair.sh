InputCSV=$1 # all abs path
CloneDir=$2
ApiKey=$3
ResultDIR=$4
FixScript=$5

timeStamp=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")

mkdir -p ${ResultDIR}/${timeStamp}
mkdir -p ${ResultDIR}/${timeStamp}/GoodPatches

mainDir=$(pwd)/scripts
logDir=$(pwd)/${ResultDIR}/${timeStamp}
patchDir=${logDir}/GoodPatches
stash=$(pwd)/scripts/cmds/stash_project.sh
DetailRes=${logDir}/DetailRes.csv
SummaryRes=${logDir}/SummaryRes.csv
unfixedCsv=${logDir}/unfixed.csv


echo "* "STARTING at $(date) 
echo "* "LOG at ${logDir}
echo "* "REPO VERSION $(git rev-parse HEAD)

exec 3>&1 4>&2
trap $(exec 2>&4 1>&3) 0 1 2 3
exec 1>$logDir/$timeStamp.log 2>&1

cd ${mainDir}
echo "* "CURRENT DIR $(pwd)

echo bash -x ${stash} ${InputCSV} projects
bash -x ${stash} ${InputCSV} projects

echo python3 ${FixScript} ${InputCSV} ${CloneDir} ${ApiKey} ${DetailRes} ${SummaryRes} ${patchDir} ${unfixedCsv} |&tee ${logDir}/main.log
python3 ${FixScript} ${InputCSV} ${CloneDir} ${ApiKey} ${DetailRes} ${SummaryRes} ${patchDir} ${unfixedCsv} |&tee ${logDir}/main.log

echo "* "ENDING at $(date)
