export const getVolumeName = function (volume) {
  let volumeName;
  if (volume) {
    if (volume.length === 4 && !isNaN(volume)) {
      volumeName = " (" + volume + ")";
    } else if (volume) {
      volumeName = " v" + volume;
    }
  } else {
    volumeName = "";
  }
  return volumeName;
};

export const getIssueName = function (issue, issueCount) {
  let issueName = "#";
  if (Number.isInteger(issue)) {
    issueName += issue.toFixed().padStart(3, "0");
  } else {
    // TODO very janky only works with single decimal
    issueName += issue.toString().padStart(5, "0");
  }
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
