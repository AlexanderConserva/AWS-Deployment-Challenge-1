# AWS-Deployment-Challenge-1

## Part 1
For part 1 I asked AI to generate me the script but there where some things that weren't correct. For example the first version of the script didn't include the session token. For the second version i asked to make the .env file auto load. After these adjustments i tried running the code but got this error: "❌ Request failed: 400 <Error><Code>InvalidRequest</Code><Message>Missing required header for this request: x-amz-content-sha256</Message>". I gave this error to AI and he knew what was wrong. AWS now requires the x-amz-content-sha256 header in SigV4 requests. After this my script works. So it is important to correctly hash the payload.
### Key Steps in SigV4 Authentication
1.	Create a Canonical Request
o	Define HTTP method, URI, headers and a hash of the payload.
o	Example in code: canonical_request variable.
2.	Create a String to Sign
o	Combine hashing algorithm, request date, credential scope and hashed canonical request.
o	Example in code: string_to_sign.
3.	Calculate the Signature
o	Take the signing key from the secret key using HMAC-SHA256 over date, region and service.
o	Example in code: get_signature_key().
4.	Add Authorization Header
o	Construct the Authorization header with signed headers and the signature.
o	Example in code: authorization_header.
5.	Send the Request
o	Use requests.get() with the signed headers.


![Part 1](images/part1-1.png)
![Part 1](images/part1-2.png)
