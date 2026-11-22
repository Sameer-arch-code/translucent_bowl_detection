# translucent_bowl_detection
Custom algorithm to detect translucent bowl or boxes 


1. Convert the image to HSV.
2. Build a binary mask of orange pixels (H 10-25, S 120-255, V 100-255).
3. Find the contours in the mask and assign IDs 1..n to the lumps.
4. Initialize an empty list of pairs.
5. For each lump A:
   5.1. Compute the center of A and the direction of its long axis.
   5.2. Set the scan direction perpendicular to the long axis.
   5.3. Scan from the center of A in both directions until the image border.
   5.4. Collect every other lump crossed by the scan line, nearest first.
   5.5. If no lump was crossed, continue with the next lump.
   5.6. Select the nearest crossed lump whose area is within +/-20% of the area of A as partner B.
   5.7. Add the pair (A, B) to the list of pairs.
6. Keep only mutual pairs, i.e. pairs (A, B) for which (B, A) is also in the list.
7. If exactly one mutual pair exists:
   7.1. Report that the bowl exists and return its pixel coordinates.
8. Else:
   8.1. Report that no bowl was found.
