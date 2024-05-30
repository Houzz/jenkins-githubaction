import os
import logging
import json
from time import time, sleep
from api4jenkins import Jenkins as OriginalJenkins

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


class Jenkins(OriginalJenkins):
    def __init__(self, url,  **kwargs):
        added_headers = kwargs.pop('added_headers', None)

        super().__init__(url, **kwargs)
        self.http_client = super().new_http_client(**kwargs +added_headers)
        # self.session = self.http_client.session
        # if added_headers:
        #     self.session.headers.update(added_headers or {})
    #
    # @property
    # def crumb(self):
    #     '''Crumb of Jenkins'''
    #     if self._crumb is None:
    #         with self._sync_lock:
    #             if self._crumb is None:
    #                 try:
    #                     _crumb = self._request(
    #                         'GET', f'{self.url}crumbIssuer/api/json').json()
    #                     self._crumb = {
    #                         _crumb['crumbRequestField']: _crumb['crumb']}
    #                 except HTTPStatusError:
    #                     self._crumb = {}
    #     return self._crumb



def main():
    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]

    # Optional
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    parameters = os.environ.get("INPUT_PARAMETERS")
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

    if parameters:
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e
    else:
        parameters = {}

    if cookies:
        try:
            cookies = json.loads(cookies)
        except json.JSONDecodeError as e:
            raise Exception('`cookies` is not valid JSON.') from e
    else:
        cookies = {}

    headers = {'Header-Name': 'Header-Value'}

    jenkins = Jenkins(url, auth=auth, cookies=cookies, added_headers=headers)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e

    logging.info('Successfully connected to Jenkins.')

    queue_item = jenkins.build_job(job_name, **parameters)

    logging.info('Requested to build job.')

    t0 = time()
    sleep(interval)
    while time() - t0 < start_timeout:
        build = queue_item.get_build()
        if build:
            break
        logging.info(f'Build not started yet. Waiting {interval} seconds.')
        sleep(interval)
    else:
        raise Exception(
            f"Could not obtain build and timed out. Waited for {start_timeout} seconds.") # noqa

    build_url = build.url
    logging.info(f"Build URL: {build_url}")
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'build_url={build_url}', file=fh)
    print(f"::notice title=build_url::{build_url}")

    if not wait:
        logging.info("Not waiting for build to finish.")
        return

    t0 = time()
    sleep(interval)
    while time() - t0 < timeout:
        result = build.result
        if result == 'SUCCESS':
            logging.info('Build successful 🎉')
            return
        elif result in ('FAILURE', 'ABORTED', 'UNSTABLE'):
            raise Exception(
                f'Build status returned "{result}". Build has failed ☹️.')
        logging.info(
            f'Build not finished yet. Waiting {interval} seconds. {build_url}')
        sleep(interval)
    else:
        raise Exception(
            f"Build has not finished and timed out. Waited for {timeout} seconds.") # noqa


if __name__ == "__main__":
    main()