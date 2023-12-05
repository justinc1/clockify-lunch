#!/usr/bin/env python
import argparse
import copy
import datetime
import logging

from clockify_api_client.client import ClockifyAPIClient
import yaml

CONF_FILE = "secrets.yml"
LOG_LEVEL = logging.DEBUG
LOG_LEVEL = logging.INFO
API_URL = 'api.clockify.me/v1'

CL_WORKSPACE_NAME = "XLAB Research"
CL_LUNCH_PROJECT_NAME = "PTO"
CL_LUNCH_TASK_NAME = "Lunch break"

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def load_conf():
    with open(CONF_FILE) as ff:
        conf = yaml.safe_load(ff)
    return conf


def filter_entries(data: list[dict], *, filt=None, start="", end=""):
    # start is day like "2023-12-04"
    # dd["timeInterval"]["start"] is like '2023-12-04T20:40:00Z'
    if filt is None:
        filt = {}
    d2 = copy.deepcopy(data)
    if filt:
        d2 = [
            dd for dd in d2
            if all([dd[kk] == filt[kk] for kk in filt])
        ]
    if start:
        d2 = [
            dd for dd in d2
            if start in dd["timeInterval"]["start"]
        ]
    if end:
        d2 = [
            dd for dd in d2
            if end in dd["timeInterval"]["end"]
        ]
    return d2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int, help="Like 2023")
    parser.add_argument("month", type=int, help="Like 11")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    # print(args)

    conf = load_conf()
    cac = ClockifyAPIClient().build(conf["API_KEY"], API_URL)

    workspaces = [ww for ww in cac.workspaces.get_workspaces() if ww["name"] == CL_WORKSPACE_NAME]
    assert len(workspaces) == 1
    workspace_id = workspaces[0]["id"]
    logger.debug(f"workspace_id={workspace_id}")

    projects = [pp for pp in cac.projects.get_projects(workspace_id) if pp["name"] == CL_LUNCH_PROJECT_NAME]
    assert len(projects) == 1
    project_id = projects[0]["id"]
    logger.debug(f"project_id={project_id}")

    tasks = [tt for tt in cac.tasks.get_tasks(workspace_id, project_id) if tt["name"] == CL_LUNCH_TASK_NAME]
    assert len(tasks) == 1
    task_id = tasks[0]["id"]
    logger.debug(f"task_id={task_id}")

    user_id = cac.users.get_current_user()["id"]
    logger.debug(f"user_id={user_id}")

    # result is already sorted, latest first
    ps = 1000
    ps = 300
    time_entries_all = cac.time_entries.get_time_entries(workspace_id, user_id, {"page-size": ps})
    # print(f"filt {filter_entries(time_entries_all, filt=dict(projectId=project_id, taskId=task_id))}")
    # time_entries_lunch = cac.time_entries.get_time_entries(workspace_id, user_id, dict(project=project_id, task=task_id))
    # print(f"time_entries_lunch={time_entries_lunch}")

    # For every workday day, if not on vacation, if no lunch break => add lunch break
    year = args.year
    month = args.month

    oldest_entry_date_str = time_entries_all[-1]["timeInterval"]["end"]
    oldest_entry_date = datetime.date.fromisoformat(oldest_entry_date_str[:10])  # "2023-01-02"
    # print(f"oldest_entry_date_str={oldest_entry_date_str}")
    earliest_edited_date = datetime.date.fromisoformat(f"{year}-{month}-01")
    # print(f"earliest_edited_date={earliest_edited_date}")
    delta_date = earliest_edited_date - oldest_entry_date
    # print(f"delta_date={delta_date}")

    # Ensure we do not add "missing" lunch only because page-size was small,
    # and existing lunch was not included into response.
    assert delta_date.days > 2

    for day in range(1, 31):
        start = f"{year}-{month}-{day:02}"
        end = f"{year}-{month}-{day:02}"
        try:
            start_date = datetime.date.fromisoformat(start)
        except ValueError as ex:
            if day in [29, 30, 31]:
                # Ignore invalid day
                continue
            raise
        te_day = filter_entries(time_entries_all, start=start)
        te_pto_day = filter_entries(te_day, filt=dict(projectId=project_id))
        te_lunch_day = filter_entries(te_day, filt=dict(projectId=project_id, taskId=task_id))
        print(f"start={start} weekday={start_date.weekday()} all_len={len(te_day)} pto_len={len(te_pto_day)} lunch_len={len(te_lunch_day)}")

        if start_date.weekday() in [5, 6]:
            # Saturday, Sunday - no lunch break
            if start_date.weekday() == 6:
                print("")
            continue

        if te_lunch_day:
            assert len(te_pto_day) == 1
            assert te_pto_day[0]["timeInterval"]["duration"] == "PT30M"  # "PT12M" is 12 minutes

        if te_pto_day:
            # any other PTO entry => lunch not needed
            # existing lunch break => do nat add again
            continue

        # We need to add lunch break
        print(f"start={start} Adding lunch break")
        payload = dict(
            projectId=project_id,
            taskId=task_id,
            start=start + "T12:00:00Z",
            end=start + "T12:30:00Z",
            description="launch-sm-se-basau",
        )
        if not DRY_RUN:
            cac.time_entries.add_time_entry(workspace_id, user_id, payload)
        # break


if __name__ == "__main__":
    main()
