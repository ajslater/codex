export const getVolumeName = function (volume) {
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

export const formattedIssue = function (decimalIssue) {
  try {
    decimalIssue = parseFloat(decimalIssue);
  } catch (error) {
    return "";
  }
  const intIssue = Math.floor(decimalIssue);
  let issueStr;
  let pad;
  if (decimalIssue === intIssue) {
    issueStr = intIssue.toString();
    pad = 4;
  } else {
    issueStr = parseFloat(decimalIssue).toFixed(1);
    pad = 6;
  }
  issueStr = issueStr.padStart(pad, "0")
  return issueStr;
};

export const getIssueName = function (issue, issueCount) {
  let issueName = "#" + formattedIssue(issue);
  if (issueCount) {
    issueName += ` of ${issueCount}`;
  }
  return issueName;
};

export const getFullComicName = function (series, volume, issue, issueCount) {
  // Format a full comic name from the series on down.
  const volumeName = getVolumeName(volume);
  const issueName = getIssueName(issue, issueCount);
  return [series, volumeName, issueName].join(" ");
};

export default {
  getFullComicName,
  getVolumeName,
  getIssueName,
};
