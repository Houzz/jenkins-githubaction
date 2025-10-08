import os
from api4jenkins import Jenkins
import logging
import json
from time import time, sleep

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def output_build_description(build):
    """Output the build description to GitHub Actions output and logs"""
    build_description = build.description if build.description else "No description available"
    logging.info(f"Build Description: {build_description}")
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'build_description={build_description}', file=fh)
    print(f"::notice title=build_description::{build_description}")


def main():
    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]

    # Optional
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    cookies = os.environ.get("INPUT_COOKIES")
    wait = bool(os.environ.get("INPUT_WAIT"))
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    start_timeout = int(os.environ.get("INPUT_START_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info(
            'Username or token not provided. Connecting without authentication.') # noqa


    if os.path.exists('/app/parameters.json'):
        with open('/app/parameters.json', 'r') as f:
            parameters = f.read()

        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e
    elif os.environ.get('INPUT_PARAMETERS'):
        parameters = os.environ.get('INPUT_PARAMETERS')
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e
    else:
        parameters = {}

    if cookies:
        try:
            cookies = json.loads(cookies.replace("'", "\""))
        except json.JSONDecodeError as e:
            raise Exception('`cookies` is not valid JSON.') from e
    else:
        cookies = {}

    jenkins = Jenkins(url, auth=auth, cookies=cookies)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e

    logging.info('Successfully connected to Jenkins.')

    jenkins.build_job(job_name, **parameters)

    logging.info('Requested to build job.')

    # get UNIQUE_GITHUB_RUN_ID from parameters
    unique_github_run_id = parameters.get('UNIQUE_GITHUB_RUN_ID', None)
    if not unique_github_run_id :
        raise Exception('GITHUB_RUN_ID not provided.')
    logging.info("GITHUB_RUN_ID: " + unique_github_run_id)

    t0 = time()

    logging.info("Waiting for job to start.")
    build = None
    last_job = None
    while time() - t0 < start_timeout:
        last_job = jenkins[job_name][f"{parameters['SERVICE']}-{parameters['ENV']}"]
        if last_job:
            if last_job.description is not None:
                if unique_github_run_id in last_job.description:
                        build = last_job
                        break
            if build:
                break
        sleep(1)
    else:
        raise Exception(f"No job with UNIQUE_GITHUB_RUN_ID={unique_github_run_id} was found. It was probably started - but I couldn't catch the URL- please check in the job page on jenkins: {url}/job/{job_name}")

    build_url = build.url
    logging.info(f"Build URL: {build_url}")
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'build_url={build_url}', file=fh)
    print(f"::notice title=build_url::{build_url}")

    if not wait:
        logging.info("Not waiting for build to finish.")
        output_build_description(build)
        return

    t0 = time()
    sleep(interval)
    while time() - t0 < timeout:
        result = build.result
        if result == 'SUCCESS':
            logging.info('Build successful 🎉')
            output_build_description(build)
            return
        elif result in ('FAILURE', 'ABORTED', 'UNSTABLE'):
            output_build_description(build)
            raise Exception(
                f'Build status returned "{result}". Build has failed ☹️.')
        logging.info(
            f'Build not finished yet. Waiting {interval} seconds. {build_url}')
        sleep(interval)
    else:
        output_build_description(build)
        raise Exception(
            f"Build has not finished and timed out. Waited for {timeout} seconds.") # noqa


if __name__ == "__main__":
    main()