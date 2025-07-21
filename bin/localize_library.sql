UPDATE codex_library
SET
	path = REPLACE(path, '/comics', @LOCAL_LIB_PATH)
WHERE
	path LIKE '/comics%';

UPDATE codex_failedimport
SET
	path = REPLACE(path, '/comics', @LOCAL_LIB_PATH)
WHERE
	path LIKE '/comics%';

UPDATE codex_comic
SET
	path = REPLACE(path, '/comics', @LOCAL_LIB_PATH)
WHERE
	path LIKE '/comics%';
