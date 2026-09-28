// Create comic names
export const formattedVolumeName = function (name, numberTo) {
  let fmtName;
  if (name != null && !Number.isNaN(name)) {
    let compoundName = name;
    if (numberTo != null && !Number.isNaN(numberTo)) {
      compoundName += "-" + numberTo;
    }
    fmtName = name.length === 4 ? `(${compoundName})` : `v${compoundName}`;
  } else {
    fmtName = "";
  }
  return fmtName;
};

export const formattedIssue = function ({ issueNumber, issueSuffix }, zeroPad) {
  let issueStr;
  try {
    if (!issueSuffix && issueNumber == undefined) {
      // Null issue defaults to display #0
      issueNumber = 0;
    }
    /*
     * parseFloat(null) was NaN but Number(null) is 0: keep a null number
     * with a suffix NaN so it still renders as the bare suffix, not "0a".
     */
    const floatIssue = issueNumber == undefined ? NaN : Number(issueNumber);
    const intIssue = Math.floor(floatIssue);
    if (zeroPad === undefined) {
      zeroPad = 0;
    }
    if (floatIssue === intIssue) {
      issueStr = intIssue.toString();
    } else {
      issueStr = floatIssue.toString();
      zeroPad += issueStr.split(".", 2)[1].length + 1;
    }
    issueStr = issueStr.padStart(zeroPad, "0");
  } catch {
    issueStr = "";
  }
  if (issueSuffix) {
    issueStr += issueSuffix;
  }

  return issueStr;
};

export const getIssueName = function (
  { issueNumber, issueSuffix, issueCount },
  zeroPad,
) {
  let issueName = "#" + formattedIssue({ issueNumber, issueSuffix }, zeroPad);
  if (issueCount) {
    issueName += ` of ${issueCount}`;
  }
  return issueName;
};

export const getFullComicName = function (
  {
    seriesName,
    volumeName,
    volumeNumberTo,
    issueNumber,
    issueSuffix,
    issueCount,
  },
  zeroPad,
) {
  // Format a full comic name from the series on down.
  const fvn = formattedVolumeName(volumeName, volumeNumberTo);
  const issueName = getIssueName(
    { issueNumber, issueSuffix, issueCount },
    zeroPad,
  );
  return [seriesName, fvn, issueName].filter(Boolean).join(" ");
};

export default {
  getFullComicName,
  formattedVolumeName,
  getIssueName,
};
