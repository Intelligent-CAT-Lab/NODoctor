inputCsv=$1 # all abs path
cloneDir=$2
apiKey=$3
resdir=$4
fixScript=$5

timeStamp=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")

mkdir -p ./${resdir}/${timeStamp}
mkdir -p ./${resdir}/${timeStamp}/goodPatches

mainDir=/home/azureuser/flaky
curDir=$(pwd)
logDir=$(pwd)/${resdir}/${timeStamp}
patchDir=${logDir}/goodPatches
stash=/home/azureuser/flaky/stash.sh
collect=$fixScript #/home/azureuser/flaky/collect_flakies.py
detailRes=${logDir}/detailRes.csv
summaryRes=${logDir}/summaryRes.csv
unfixedCsv=${logDir}/unfixed.csv


echo "* "STARTING at $(date) 
echo "* "LOG at ${logDir}
echo "* "REPO VERSION $(git rev-parse HEAD)

exec 3>&1 4>&2
trap $(exec 2>&4 1>&3) 0 1 2 3
exec 1>$logDir/$timeStamp.log 2>&1

cd ${mainDir}
echo "* "CURRENT DIR $(pwd)

echo bash -x ${stash} ${inputCsv} projects
bash -x ${stash} ${inputCsv} projects

echo python3 ${collect} ${inputCsv} ${cloneDir} ${apiKey} ${detailRes} ${summaryRes} ${patchDir} ${unfixedCsv} |&tee ${logDir}/main.log
python3 ${collect} ${inputCsv} ${cloneDir} ${apiKey} ${detailRes} ${summaryRes} ${patchDir} ${unfixedCsv} |&tee ${logDir}/main.log

echo "* "ENDING at $(date)