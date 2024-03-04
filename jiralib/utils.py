import requests
from urllib.parse import urlparse


def open_jira_session(url, username, password, verify_ssl=True):
    auth_url = '{uri.scheme}://{uri.netloc}/rest/auth/1/session'.format(uri=urlparse(url))
    auth = {'username': username, 'password': password}
    resp = requests.post(auth_url, json=auth, verify=verify_ssl)
    return resp.json()['session'] if resp.ok else None


def close_jira_session(url, session, verify_ssl=True):
    auth_url = '{uri.scheme}://{uri.netloc}/rest/auth/1/session'.format(uri=urlparse(url))
    cookies = {session['name']: session['value']}
    resp = requests.delete(auth_url, cookies=cookies, verify=verify_ssl)
    return resp.ok


def select_issues(jira, filter, fields, expand=None, chunk_size=50):
    issues = []
    i = 0
    while True:
        chunk = jira.jql(filter, start=i, limit=chunk_size, fields=fields, expand=expand)
        i += len(chunk['issues'])
        issues += chunk['issues']
        if i >= chunk['total']:
            break
    return issues


def select_issues_for_board(jira, board_id, filter, fields, expand=None, chunk_size=50):
    issues = []
    i = 0
    while True:
        chunk = jira.get_issues_for_board(board_id, filter, start=i, limit=chunk_size, fields=fields, expand=expand)
        i += len(chunk['issues'])
        issues += chunk['issues']
        if i >= chunk['total']:
            break
    return issues


if __name__ == '__main__':

    from atlassian import Jira

    #    import requests
    #    from urllib.parse import urlparse
    #    from jira_utils import open_jira_session, close_jira_session, select_issues_for_board

    def test_auth():
        url = 'https://jira.sberbank.ru/'
        session = open_jira_session(url, verify_ssl=False)
        jira = Jira(url=url, cookies={session['name']: session['value']}, verify_ssl=False)
        issue = jira.issue('GTP-8019')
        print(f"Issue для проверки авториpации {issue['key']}")

        if close_jira_session(url, session, verify_ssl=False):
            print('Сессия закрыта')
        else:
            print('Сессия не закрыта')
        issue = jira.issue('GTP-8019')

        print(f"Issue для проверки logout {issue['key']}")


    def test_select_issues_for_board():
        import board

        url = 'https://jira.sberbank.ru/'
        board_id = 33899

        session = open_jira_session(url, verify_ssl=False)
        jira = Jira(url=url, cookies={session['name']: session['value']}, verify_ssl=False)
        issues = select_issues_for_board(jira, board_id,
                                         '((statusCategory = Done AND status changed AFTER -12w) OR (statusCategory != Done)) AND (IssueType in (Bug, Story, Task))',
                                         fields=['summary', 'status', 'created'], expand='changelog')

        print(f'Selected {len(issues)} issues')
        board_config = jira.get_agile_board_configuration(board_id)

        close_jira_session(url, session, False)
        board = board.Board(board_config)
        df_issues = board.project_issues(issues)

        # df_issues['link'] = df_issues.apply(
        #     lambda row: "{uri.scheme}://{uri.netloc}/browse/{id}".format(uri=urlparse(row['link']), id=row['key']),
        #     axis=1)
        # df_issues.rename(columns={'key': 'id'}, inplace=True)
        # df_issues.set_index('id', inplace=True)

        df_issues.to_csv('PESO.csv')
        print('Экспорт завершен')

        print(df_issues)

test_select_issues_for_board()
