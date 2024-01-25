project=$1
sha=$2
module=$3
polluterFormatTest=$4
victimFormatTest=$5
cloneDir=$6
tag=$7
times=$8

#project,sha,module,polluter_format_test,victim_format_test,cloneDir,tag,times
mkdir -p ./output_run_id/verify_patches_surefire_logs/${project}_${sha}/${test}/${tag}

mainDir=${cloneDir}
curDir=$(pwd)
logDir=$(pwd)/output_run2/verify_patches_surefire_logs/${project}_${sha}/${test}/${tag}


run_test(){
    echo mvn test -pl ${module} -Dsurefire.runOrder=testorder -Dtest=${polluterFormatTest},${victimFormatTest} -Drat.skip -Dcheckstyle.skip -Denforcer.skip=true -Dspotbugs.skip -Dmaven.test.failure.ignore=true -Djacoco.skip -Danimal.sniffer.skip -Dmaven.antrun.skip -Djacoco.skip --log-file ${logDir}/"$1".log
    mvn test -pl ${module} -Dsurefire.runOrder=testorder -Dtest=${polluterFormatTest},${victimFormatTest} -Drat.skip -Dcheckstyle.skip -Denforcer.skip=true -Dspotbugs.skip -Dmaven.test.failure.ignore=true -Djacoco.skip -Danimal.sniffer.skip -Dmaven.antrun.skip -Djacoco.skip --log-file ${logDir}/"$1".log
}

echo STARTING at $(date)
git rev-parse HEAD

echo ${mainDir}/${sha}/${project}
cd ${mainDir}/${sha}/${project}
java_version="$(grep "<jdk.*>" pom.xml)"
if [[ $java_version == *"11"* ]]; then
    echo "java version 11"
    export JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
elif [[ $java_version == *"8"* ]]; then
    echo "java version 8"
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
elif [[ $java_version == *"1.8"* ]]; then
    echo "java version 8"
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
else
    echo "java version:" $java_version
    export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH
fi

echo CURRENT DIR $(pwd)
for i in {1..${times}}
do
    run_test ${i}
done

cd ${curDir}
echo ENDING at $(date)