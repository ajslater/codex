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

export const formattedIssue = function (decimalIssue, issueSuffix) {
  if (decimalIssue == undefined) {
    return;
  }
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
  issueStr = issueStr.padStart(pad, "0") + issueSuffix;
  return issueStr;
};

export const getIssueName = function (issue, issueSuffix, issueCount) {
  if (issue == undefined) {
    return "";
  }
  let issueName = "#" + formattedIssue(issue, issueSuffix);
  if (issueCount) {
    issueName += ` of ${issueCount}`;
  }
  return issueName;
};

export const getFullComicName = function ({
  seriesName,
  volumeName,
  issue,
  issueSuffix,
  issueCount,
}) {
  // Format a full comic name from the series on down.
  const fvn = formattedVolumeName(volumeName);
  const issueName = getIssueName(issue, issueSuffix, issueCount);
  return [seriesName, fvn, issueName].join(" ");
};

export default {
  getFullComicName,
  formattedVolumeName,
  getIssueName,
};
