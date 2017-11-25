How to delete account data manually:

> docker exec -it nylassyncdocker_sync-engine_1 bash

> ./bin/inbox-console -e some-email@deepframe.io

> In [1]: account.disable_sync("account deleted")
>
> In [2]: db_session.commit()
>
> In [3]: exit

> ./bin/delete-account-data 1 --yes
