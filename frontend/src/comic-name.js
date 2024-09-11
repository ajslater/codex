// Create comic names
export const formattedVolumeName = function (volume) {
  let volumeName;
  if (volume) {
    volumeName =
      volume.length === 4 && !Number.isNaN(volume)
        ? "(" + volume + ")"
        : "v" + volume;
  } else {
    volumeName = "";
  }
  return volumeName;
};

export const formattedIssue = function ({ issueNumber, issueSuffix }, zeroPad) {
  let issueStr;
  try {
    if (issueNumber == undefined && !issueSuffix) {
      // Null issue defaults to display #0
      issueNumber = 0;
    }
    const floatIssue = Number.parseFloat(issueNumber);
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
  { seriesName, volumeName, issueNumber, issueSuffix, issueCount },
  zeroPad,
) {
  // Format a full comic name from the series on down.
  const fvn = formattedVolumeName(volumeName);
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
