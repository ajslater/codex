export const formattedVolumeName = function (volume) {
  let volumeName;
  if (!volume) {
    volumeName = "";
  } else {
    volumeName =
      volume.length === 4 && !Number.isNaN(volume)
        ? " (" + volume + ")"
        : " v" + volume;
  }
  return volumeName;
};

export const formattedIssue = function ({ issue, issueSuffix }, zeroPad) {
  if (issue == undefined) {
    return;
  }
  let issueStr;
  try {
    const floatIssue = Number.parseFloat(issue);
    const intIssue = Math.floor(floatIssue);
    if (zeroPad === undefined) {
      zeroPad = 0;
    }
    // TODO move out to browser Page only.
    if (floatIssue === intIssue) {
      issueStr = intIssue.toString();
    } else {
      issueStr = floatIssue.toString();
      zeroPad += issueStr.split(".")[1].length + 1;
    }
    issueStr = issueStr.padStart(zeroPad, "0") + issueSuffix;
  } catch {
    issueStr = "";
  }

  return issueStr;
};

export const getIssueName = function (
  { issue, issueSuffix, issueCount },
  zeroPad
) {
  if (issue == undefined) {
    return "";
  }
  let issueName = "#" + formattedIssue({ issue, issueSuffix }, zeroPad);
  if (issueCount) {
    issueName += ` of ${issueCount}`;
  }
  return issueName;
};

export const getFullComicName = function (
  { seriesName, volumeName, issue, issueSuffix, issueCount },
  zeroPad
) {
  // Format a full comic name from the series on down.
  const fvn = formattedVolumeName(volumeName);
  const issueName = getIssueName({ issue, issueSuffix, issueCount }, zeroPad);
  return [seriesName, fvn, issueName].join(" ");
};

export default {
  getFullComicName,
  formattedVolumeName,
  getIssueName,
};
