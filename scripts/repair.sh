InputCSV=$1 # all abs path
CloneDir=$2
ResultDIR=$3

timeStamp=$(echo -n $(date "+%Y-%m-%d %H:%M:%S") | shasum | cut -f 1 -d " ")

ResultDIR="${ResultDIR%/}"
mkdir -p ${ResultDIR}/${timeStamp}
OutputDIR=${ResultDIR}/${timeStamp}/outputs
mkdir -p ${OutputDIR}

echo "* "STARTING at $(date) 
echo "* "LOG at ${OutputDIR}
echo "* "REPO VERSION $(git rev-parse HEAD)

exec 3>&1 4>&2
trap $(exec 2>&4 1>&3) 0 1 2 3
exec 1>${OutputDIR}/${timeStamp}.log 2>&1

FixScript=scripts/NODRepair.py
echo "* CURRENT DIR ${pwd}"


echo "* Running with ${FixScript} ${InputCSV} ${CloneDir} ${OutputDIR} |&tee ${OutputDIR}/main.log"
python3 ${FixScript} --input_csv ${InputCSV} --clone_dir ${CloneDir} --output_dir ${OutputDIR} |&tee ${OutputDIR}/main.log

echo "* "ENDING at $(date)
