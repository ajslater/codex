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
  if (decimalIssue === undefined || decimalIssue === null) {
    return;
  }
  const intIssue = Math.floor(decimalIssue);
  let issueStr = intIssue.toString().padStart(3, "0");
  if (decimalIssue - intIssue === 0.5) {
    if (intIssue === 0) {
      issueStr = "";
    }
    issueStr += "½";
  } else if (decimalIssue !== intIssue) {
    const remainder = decimalIssue - intIssue;
    const decimalSuffix = remainder.toString().slice(1);
    issueStr += decimalSuffix;
  }
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
