## System Configuration
- The backend server runs on 7001 port
- Virtual environment (venv) is located in project root directory, not in backend folder
- Always start backend with ./start_backend.sh

## Test Configuration
- Test user email: test@ioflow.com
- Test user password: test123456
- All test scripts should use credentials from test-script/test_config.py
- Run `python3 test-script/create_test_user_sqlite.py` to create test user before running tests
- all mcp tool must use mcp api  bridge to get the information from api, as the mcp server run on a remote machine
- mcp bridge should not have business logic, it is a thin wrapper which routes mcp call to api call