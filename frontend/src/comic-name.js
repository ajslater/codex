// Create comic names
export const formattedVolumeName = function (volume) {
  let volumeName;
  if (volume) {
    volumeName =
      volume.length === 4 && !Number.isNaN(volume)
        ? " (" + volume + ")"
        : " v" + volume;
  } else {
    volumeName = "";
  }
  return volumeName;
};

export const formattedIssue = function ({ issue, issueSuffix }, zeroPad) {
  let issueStr;
  try {
    if (issue == undefined && !issueSuffix) {
      // Null issue defaults to display #0
      issue = 0;
    }
    const floatIssue = Number.parseFloat(issue);
    const intIssue = Math.floor(floatIssue);
    if (zeroPad === undefined) {
      zeroPad = 0;
    }
    if (floatIssue === intIssue) {
      issueStr = intIssue.toString();
    } else {
      issueStr = floatIssue.toString();
      zeroPad += issueStr.split(".")[1].length + 1;
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
  { issue, issueSuffix, issueCount },
  zeroPad
) {
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
  return [seriesName, fvn, issueName].filter(Boolean).join(" ");
};

export default {
  getFullComicName,
  formattedVolumeName,
  getIssueName,
};
