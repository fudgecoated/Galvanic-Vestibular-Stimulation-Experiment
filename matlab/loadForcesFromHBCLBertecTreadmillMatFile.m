function [forcesAndMoments] = loadForcesFromHBCLBertecTreadmillMatFile(matFilename, varargin)
%loadForcesFromHBCLBertecTreadmillMatFile calculates forces and moments
% from the HBCL's bertec treadmill saved mat files

shouldFilter = 1;
forceFrequency = 960;
filterCutoffFrequency = 25;

for i = 1 : 2 : length(varargin)
  option = varargin{i};
  value = varargin{i + 1};
  switch option
    case 'shouldFilter'
      shouldFilter = value;
    case 'forceFrequency'
      forceFrequency = value;
    case 'filterCutoffFrequency'
      filterCutoffFrequency = value;
  end
end


%%
load(matFilename);

[bForce, aForce] = butter(3, filterCutoffFrequency * 2 / forceFrequency);

forceCalibrationMatrix = diag([500 500 1000]);
momentCalibrationMatrix = diag([800 250 400]);

if (shouldFilter)
  grabSignals = @(indeces) filtfilt(bForce, aForce, samples(:, indeces));
else
  grabSignals = @(indeces) samples(:, indeces);
end  

forcesAndMoments.left.groundReactionForces = grabSignals([1 2 3]) * forceCalibrationMatrix;
forcesAndMoments.left.groundReactionMoments = grabSignals([4 5 6]) * momentCalibrationMatrix;
forcesAndMoments.right.groundReactionForces = grabSignals([9 10 11]) * forceCalibrationMatrix;
forcesAndMoments.right.groundReactionMoments = grabSignals([12 13 14]) * momentCalibrationMatrix;


end

