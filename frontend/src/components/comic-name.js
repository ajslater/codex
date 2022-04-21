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
  if (decimalIssue == null) { return null;}
  try {
    decimalIssue = Number.parseFloat(decimalIssue);
  } catch {
    return "";
  }
  const intIssue = Math.floor(decimalIssue);
  let issueStr;
  let pad;
  if (decimalIssue === intIssue) {
    issueStr = intIssue.toString();
    pad = 3;
  } else {
    issueStr = Number.parseFloat(decimalIssue).toFixed(1);
    pad = 5;
  }
  issueStr = issueStr.padStart(pad, "0");
  return issueStr;
};

export const getIssueName = function (issue, issueCount) {
  if (issue == null) { return "";}
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
