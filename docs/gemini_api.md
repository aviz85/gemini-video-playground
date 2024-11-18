## Initial example
````
import os
import time
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def upload_to_gemini(path, mime_type=None):
  """Uploads the given file to Gemini.

  See https://ai.google.dev/gemini-api/docs/prompting_with_media
  """
  file = genai.upload_file(path, mime_type=mime_type)
  print(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file

def wait_for_files_active(files):
  """Waits for the given files to be active.

  Some files uploaded to the Gemini API need to be processed before they can be
  used as prompt inputs. The status can be seen by querying the file's "state"
  field.

  This implementation uses a simple blocking polling loop. Production code
  should probably employ a more sophisticated approach.
  """
  print("Waiting for file processing...")
  for name in (file.name for file in files):
    file = genai.get_file(name)
    while file.state.name == "PROCESSING":
      print(".", end="", flush=True)
      time.sleep(10)
      file = genai.get_file(name)
    if file.state.name != "ACTIVE":
      raise Exception(f"File {file.name} failed to process")
  print("...all files ready")
  print()

# Create the model
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
  model_name="gemini-exp-1114",
  generation_config=generation_config,
)

# TODO Make these files available on the local file system
# You may need to update the file paths
files = [
  upload_to_gemini("3b98fa27-8a60-45aa-85e6-895d9ce4da25.share.MP4", mime_type="video/mp4")
]

# Some files have a processing delay. Wait for them to be ready.
wait_for_files_active(files)

chat_session = model.start_chat(
  history=[
    {
      "role": "user",
      "parts": [
        files[0],
      ],
    },
    {
      "role": "model",
      "parts": [
        files[1],
      ],
    },
    {
      "role": "user",
      "parts": [
        "what in the video?",
      ],
    },
    {
      "role": "model",
      "parts": [
        files[2],
      ],
    },
  ]
)

response = chat_session.send_message("INSERT_INPUT_HERE")

print(response.text)
````

## Models
Method: models.list
Lists the Models available through the Gemini API.

Endpoint
get
https://generativelanguage.googleapis.com/v1beta/models

Query parameters
pageSize
integer
The maximum number of Models to return (per page).

If unspecified, 50 models will be returned per page. This method returns at most 1000 models per page, even if you pass a larger pageSize.

pageToken
string
A page token, received from a previous models.list call.

Provide the pageToken returned by one request as an argument to the next request to retrieve the next page.

When paginating, all other parameters provided to models.list must match the call that provided the page token.

Request body
The request body must be empty.

Example request
Python
Shell

print("List of models that support generateContent:\n")
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)

print("List of models that support embedContent:\n")
for m in genai.list_models():
    if "embedContent" in m.supported_generation_methods:
        print(m.name)
Response body
Response from ListModel containing a paginated list of Models.

If successful, the response body contains data with the following structure:

Fields
models[]
object (Model)
The returned Models.

nextPageToken
string
A token, which can be sent as pageToken to retrieve the next page.

If this field is omitted, there are no more pages.

JSON representation

{
  "models": [
    {
      object (Model)
    }
  ],
  "nextPageToken": string
}
REST Resource: models
Resource: Model
Information about a Generative Language Model.

Fields
name
string
Required. The resource name of the Model. Refer to Model variants for all allowed values.

Format: models/{model} with a {model} naming convention of:

"{baseModelId}-{version}"
Examples:

models/gemini-1.5-flash-001
baseModelId
string
Required. The name of the base model, pass this to the generation request.

Examples:

gemini-1.5-flash
version
string
Required. The version number of the model.

This represents the major version (1.0 or 1.5)

displayName
string
The human-readable name of the model. E.g. "Gemini 1.5 Flash".

The name can be up to 128 characters long and can consist of any UTF-8 characters.

description
string
A short description of the model.

inputTokenLimit
integer
Maximum number of input tokens allowed for this model.

outputTokenLimit
integer
Maximum number of output tokens available for this model.

supportedGenerationMethods[]
string
The model's supported generation methods.

The corresponding API method names are defined as Pascal case strings, such as generateMessage and generateContent.

temperature
number
Controls the randomness of the output.

Values can range over [0.0,maxTemperature], inclusive. A higher value will produce responses that are more varied, while a value closer to 0.0 will typically result in less surprising responses from the model. This value specifies default to be used by the backend while making the call to the model.

maxTemperature
number
The maximum temperature this model can use.

topP
number
For Nucleus sampling.

Nucleus sampling considers the smallest set of tokens whose probability sum is at least topP. This value specifies default to be used by the backend while making the call to the model.

topK
integer
For Top-k sampling.

Top-k sampling considers the set of topK most probable tokens. This value specifies default to be used by the backend while making the call to the model. If empty, indicates the model doesn't use top-k sampling, and topK isn't allowed as a generation parameter.

JSON representation

{
  "name": string,
  "baseModelId": string,
  "version": string,
  "displayName": string,
  "description": string,
  "inputTokenLimit": integer,
  "outputTokenLimit": integer,
  "supportedGenerationMethods": [
    string
  ],
  "temperature": number,
  "maxTemperature": number,
  "topP": number,
  "topK": integer
}

## Generating content 

bookmark_border


The Gemini API supports content generation with images, audio, code, tools, and more. For details on each of these features, read on and check out the task-focused sample code, or read the comprehensive guides.

Text generation
Vision
Audio
Long context
Code execution
JSON Mode
Function calling
System instructions
Method: models.generateContent
Generates a model response given an input GenerateContentRequest. Refer to the text generation guide for detailed usage information. Input capabilities differ between models, including tuned models. Refer to the model guide and tuning guide for details.

Endpoint
post
https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent

Path parameters
model
string
Required. The name of the Model to use for generating the completion.

Format: name=models/{model}. It takes the form models/{model}.

Request body
The request body contains data with the following structure:

Fields
contents[]
object (Content)
Required. The content of the current conversation with the model.

For single-turn queries, this is a single instance. For multi-turn queries like chat, this is a repeated field that contains the conversation history and the latest request.

tools[]
object (Tool)
Optional. A list of Tools the Model may use to generate the next response.

A Tool is a piece of code that enables the system to interact with external systems to perform an action, or set of actions, outside of knowledge and scope of the Model. Supported Tools are Function and codeExecution. Refer to the Function calling and the Code execution guides to learn more.

toolConfig
object (ToolConfig)
Optional. Tool configuration for any Tool specified in the request. Refer to the Function calling guide for a usage example.

safetySettings[]
object (SafetySetting)
Optional. A list of unique SafetySetting instances for blocking unsafe content.

This will be enforced on the GenerateContentRequest.contents and GenerateContentResponse.candidates. There should not be more than one setting for each SafetyCategory type. The API will block any contents and responses that fail to meet the thresholds set by these settings. This list overrides the default settings for each SafetyCategory specified in the safetySettings. If there is no SafetySetting for a given SafetyCategory provided in the list, the API will use the default safety setting for that category. Harm categories HARM_CATEGORY_HATE_SPEECH, HARM_CATEGORY_SEXUALLY_EXPLICIT, HARM_CATEGORY_DANGEROUS_CONTENT, HARM_CATEGORY_HARASSMENT are supported. Refer to the guide for detailed information on available safety settings. Also refer to the Safety guidance to learn how to incorporate safety considerations in your AI applications.

systemInstruction
object (Content)
Optional. Developer set system instruction(s). Currently, text only.

generationConfig
object (GenerationConfig)
Optional. Configuration options for model generation and outputs.

cachedContent
string
Optional. The name of the content cached to use as context to serve the prediction. Format: cachedContents/{cachedContent}

Example request
Text
Image
Audio
Video
PDF
Chat
Cache
Tuned Model
More
Python
Node.js
Go
Shell
Kotlin
Swift
Dart
Java

model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Write a story about a magic backpack.")
print(response.text)
Response body
If successful, the response body contains an instance of GenerateContentResponse.

Method: models.streamGenerateContent
Generates a streamed response from the model given an input GenerateContentRequest.

Endpoint
post
https://generativelanguage.googleapis.com/v1beta/{model=models/*}:streamGenerateContent

Path parameters
model
string
Required. The name of the Model to use for generating the completion.

Format: name=models/{model}. It takes the form models/{model}.

Request body
The request body contains data with the following structure:

Fields
contents[]
object (Content)
Required. The content of the current conversation with the model.

For single-turn queries, this is a single instance. For multi-turn queries like chat, this is a repeated field that contains the conversation history and the latest request.

tools[]
object (Tool)
Optional. A list of Tools the Model may use to generate the next response.

A Tool is a piece of code that enables the system to interact with external systems to perform an action, or set of actions, outside of knowledge and scope of the Model. Supported Tools are Function and codeExecution. Refer to the Function calling and the Code execution guides to learn more.

toolConfig
object (ToolConfig)
Optional. Tool configuration for any Tool specified in the request. Refer to the Function calling guide for a usage example.

safetySettings[]
object (SafetySetting)
Optional. A list of unique SafetySetting instances for blocking unsafe content.

This will be enforced on the GenerateContentRequest.contents and GenerateContentResponse.candidates. There should not be more than one setting for each SafetyCategory type. The API will block any contents and responses that fail to meet the thresholds set by these settings. This list overrides the default settings for each SafetyCategory specified in the safetySettings. If there is no SafetySetting for a given SafetyCategory provided in the list, the API will use the default safety setting for that category. Harm categories HARM_CATEGORY_HATE_SPEECH, HARM_CATEGORY_SEXUALLY_EXPLICIT, HARM_CATEGORY_DANGEROUS_CONTENT, HARM_CATEGORY_HARASSMENT are supported. Refer to the guide for detailed information on available safety settings. Also refer to the Safety guidance to learn how to incorporate safety considerations in your AI applications.

systemInstruction
object (Content)
Optional. Developer set system instruction(s). Currently, text only.

generationConfig
object (GenerationConfig)
Optional. Configuration options for model generation and outputs.

cachedContent
string
Optional. The name of the content cached to use as context to serve the prediction. Format: cachedContents/{cachedContent}

Example request
Text
Image
Audio
Video
PDF
Chat
Python
Node.js
Go
Shell
Kotlin
Swift
Dart
Java

model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Write a story about a magic backpack.", stream=True)
for chunk in response:
    print(chunk.text)
    print("_" * 80)
Response body
If successful, the response body contains a stream of GenerateContentResponse instances.

GenerateContentResponse
Response from the model supporting multiple candidate responses.

Safety ratings and content filtering are reported for both prompt in GenerateContentResponse.prompt_feedback and for each candidate in finishReason and in safetyRatings. The API: - Returns either all requested candidates or none of them - Returns no candidates at all only if there was something wrong with the prompt (check promptFeedback) - Reports feedback on each candidate in finishReason and safetyRatings.

Fields
candidates[]
object (Candidate)
Candidate responses from the model.

promptFeedback
object (PromptFeedback)
Returns the prompt's feedback related to the content filters.

usageMetadata
object (UsageMetadata)
Output only. Metadata on the generation requests' token usage.

JSON representation

{
  "candidates": [
    {
      object (Candidate)
    }
  ],
  "promptFeedback": {
    object (PromptFeedback)
  },
  "usageMetadata": {
    object (UsageMetadata)
  }
}
PromptFeedback
A set of the feedback metadata the prompt specified in GenerateContentRequest.content.

Fields
blockReason
enum (BlockReason)
Optional. If set, the prompt was blocked and no candidates are returned. Rephrase the prompt.

safetyRatings[]
object (SafetyRating)
Ratings for safety of the prompt. There is at most one rating per category.

JSON representation

{
  "blockReason": enum (BlockReason),
  "safetyRatings": [
    {
      object (SafetyRating)
    }
  ]
}
BlockReason
Specifies the reason why the prompt was blocked.

Enums
BLOCK_REASON_UNSPECIFIED	Default value. This value is unused.
SAFETY	Prompt was blocked due to safety reasons. Inspect safetyRatings to understand which safety category blocked it.
OTHER	Prompt was blocked due to unknown reasons.
BLOCKLIST	Prompt was blocked due to the terms which are included from the terminology blocklist.
PROHIBITED_CONTENT	Prompt was blocked due to prohibited content.
UsageMetadata
Metadata on the generation request's token usage.

Fields
promptTokenCount
integer
Number of tokens in the prompt. When cachedContent is set, this is still the total effective prompt size meaning this includes the number of tokens in the cached content.

cachedContentTokenCount
integer
Number of tokens in the cached part of the prompt (the cached content)

candidatesTokenCount
integer
Total number of tokens across all the generated response candidates.

totalTokenCount
integer
Total token count for the generation request (prompt + response candidates).

JSON representation

{
  "promptTokenCount": integer,
  "cachedContentTokenCount": integer,
  "candidatesTokenCount": integer,
  "totalTokenCount": integer
}
Candidate
A response candidate generated from the model.

Fields
content
object (Content)
Output only. Generated content returned from the model.

finishReason
enum (FinishReason)
Optional. Output only. The reason why the model stopped generating tokens.

If empty, the model has not stopped generating tokens.

safetyRatings[]
object (SafetyRating)
List of ratings for the safety of a response candidate.

There is at most one rating per category.

citationMetadata
object (CitationMetadata)
Output only. Citation information for model-generated candidate.

This field may be populated with recitation information for any text included in the content. These are passages that are "recited" from copyrighted material in the foundational LLM's training data.

tokenCount
integer
Output only. Token count for this candidate.

groundingAttributions[]
object (GroundingAttribution)
Output only. Attribution information for sources that contributed to a grounded answer.

This field is populated for GenerateAnswer calls.

groundingMetadata
object (GroundingMetadata)
Output only. Grounding metadata for the candidate.

This field is populated for GenerateContent calls.

avgLogprobs
number
Output only.

logprobsResult
object (LogprobsResult)
Output only. Log-likelihood scores for the response tokens and top tokens

index
integer
Output only. Index of the candidate in the list of response candidates.

JSON representation

{
  "content": {
    object (Content)
  },
  "finishReason": enum (FinishReason),
  "safetyRatings": [
    {
      object (SafetyRating)
    }
  ],
  "citationMetadata": {
    object (CitationMetadata)
  },
  "tokenCount": integer,
  "groundingAttributions": [
    {
      object (GroundingAttribution)
    }
  ],
  "groundingMetadata": {
    object (GroundingMetadata)
  },
  "avgLogprobs": number,
  "logprobsResult": {
    object (LogprobsResult)
  },
  "index": integer
}
FinishReason
Defines the reason why the model stopped generating tokens.

Enums
FINISH_REASON_UNSPECIFIED	Default value. This value is unused.
STOP	Natural stop point of the model or provided stop sequence.
MAX_TOKENS	The maximum number of tokens as specified in the request was reached.
SAFETY	The response candidate content was flagged for safety reasons.
RECITATION	The response candidate content was flagged for recitation reasons.
LANGUAGE	The response candidate content was flagged for using an unsupported language.
OTHER	Unknown reason.
BLOCKLIST	Token generation stopped because the content contains forbidden terms.
PROHIBITED_CONTENT	Token generation stopped for potentially containing prohibited content.
SPII	Token generation stopped because the content potentially contains Sensitive Personally Identifiable Information (SPII).
MALFORMED_FUNCTION_CALL	The function call generated by the model is invalid.
GroundingAttribution
Attribution for a source that contributed to an answer.

Fields
sourceId
object (AttributionSourceId)
Output only. Identifier for the source contributing to this attribution.

content
object (Content)
Grounding source content that makes up this attribution.

JSON representation

{
  "sourceId": {
    object (AttributionSourceId)
  },
  "content": {
    object (Content)
  }
}
AttributionSourceId
Identifier for the source contributing to this attribution.

Fields
Union field source.

source can be only one of the following:

groundingPassage
object (GroundingPassageId)
Identifier for an inline passage.

semanticRetrieverChunk
object (SemanticRetrieverChunk)
Identifier for a Chunk fetched via Semantic Retriever.

JSON representation

{

  // Union field source can be only one of the following:
  "groundingPassage": {
    object (GroundingPassageId)
  },
  "semanticRetrieverChunk": {
    object (SemanticRetrieverChunk)
  }
  // End of list of possible types for union field source.
}
GroundingPassageId
Identifier for a part within a GroundingPassage.

Fields
passageId
string
Output only. ID of the passage matching the GenerateAnswerRequest's GroundingPassage.id.

partIndex
integer
Output only. Index of the part within the GenerateAnswerRequest's GroundingPassage.content.

JSON representation

{
  "passageId": string,
  "partIndex": integer
}
SemanticRetrieverChunk
Identifier for a Chunk retrieved via Semantic Retriever specified in the GenerateAnswerRequest using SemanticRetrieverConfig.

Fields
source
string
Output only. Name of the source matching the request's SemanticRetrieverConfig.source. Example: corpora/123 or corpora/123/documents/abc

chunk
string
Output only. Name of the Chunk containing the attributed text. Example: corpora/123/documents/abc/chunks/xyz

JSON representation

{
  "source": string,
  "chunk": string
}
GroundingMetadata
Metadata returned to client when grounding is enabled.

Fields
groundingChunks[]
object (GroundingChunk)
List of supporting references retrieved from specified grounding source.

groundingSupports[]
object (GroundingSupport)
List of grounding support.

webSearchQueries[]
string
Web search queries for the following-up web search.

searchEntryPoint
object (SearchEntryPoint)
Optional. Google search entry for the following-up web searches.

retrievalMetadata
object (RetrievalMetadata)
Metadata related to retrieval in the grounding flow.

JSON representation

{
  "groundingChunks": [
    {
      object (GroundingChunk)
    }
  ],
  "groundingSupports": [
    {
      object (GroundingSupport)
    }
  ],
  "webSearchQueries": [
    string
  ],
  "searchEntryPoint": {
    object (SearchEntryPoint)
  },
  "retrievalMetadata": {
    object (RetrievalMetadata)
  }
}
SearchEntryPoint
Google search entry point.

Fields
renderedContent
string
Optional. Web content snippet that can be embedded in a web page or an app webview.

sdkBlob
string (bytes format)
Optional. Base64 encoded JSON representing array of <search term, search url> tuple.

A base64-encoded string.

JSON representation

{
  "renderedContent": string,
  "sdkBlob": string
}
GroundingChunk
Grounding chunk.

Fields
Union field
chunk_type
. Chunk type.
chunk_type
can be only one of the following:
web
object (Web)
Grounding chunk from the web.

JSON representation

{

  // Union field chunk_type can be only one of the following:
  "web": {
    object (Web)
  }
  // End of list of possible types for union field chunk_type.
}
Web
Chunk from the web.

Fields
uri
string
URI reference of the chunk.

title
string
Title of the chunk.

JSON representation

{
  "uri": string,
  "title": string
}
GroundingSupport
Grounding support.

Fields
groundingChunkIndices[]
integer
A list of indices (into 'grounding_chunk') specifying the citations associated with the claim. For instance [1,3,4] means that grounding_chunk[1], grounding_chunk[3], grounding_chunk[4] are the retrieved content attributed to the claim.

confidenceScores[]
number
Confidence score of the support references. Ranges from 0 to 1. 1 is the most confident. This list must have the same size as the groundingChunkIndices.

segment
object (Segment)
Segment of the content this support belongs to.

JSON representation

{
  "groundingChunkIndices": [
    integer
  ],
  "confidenceScores": [
    number
  ],
  "segment": {
    object (Segment)
  }
}
Segment
Segment of the content.

Fields
partIndex
integer
Output only. The index of a Part object within its parent Content object.

startIndex
integer
Output only. Start index in the given Part, measured in bytes. Offset from the start of the Part, inclusive, starting at zero.

endIndex
integer
Output only. End index in the given Part, measured in bytes. Offset from the start of the Part, exclusive, starting at zero.

text
string
Output only. The text corresponding to the segment from the response.

JSON representation

{
  "partIndex": integer,
  "startIndex": integer,
  "endIndex": integer,
  "text": string
}
RetrievalMetadata
Metadata related to retrieval in the grounding flow.

Fields
googleSearchDynamicRetrievalScore
number
Optional. Score indicating how likely information from google search could help answer the prompt. The score is in the range [0, 1], where 0 is the least likely and 1 is the most likely. This score is only populated when google search grounding and dynamic retrieval is enabled. It will be compared to the threshold to determine whether to trigger google search.

JSON representation

{
  "googleSearchDynamicRetrievalScore": number
}
LogprobsResult
Logprobs Result

Fields
topCandidates[]
object (TopCandidates)
Length = total number of decoding steps.

chosenCandidates[]
object (Candidate)
Length = total number of decoding steps. The chosen candidates may or may not be in topCandidates.

JSON representation

{
  "topCandidates": [
    {
      object (TopCandidates)
    }
  ],
  "chosenCandidates": [
    {
      object (Candidate)
    }
  ]
}
TopCandidates
Candidates with top log probabilities at each decoding step.

Fields
candidates[]
object (Candidate)
Sorted by log probability in descending order.

JSON representation

{
  "candidates": [
    {
      object (Candidate)
    }
  ]
}
Candidate
Candidate for the logprobs token and score.

Fields
token
string
The candidate’s token string value.

tokenId
integer
The candidate’s token id value.

logProbability
number
The candidate's log probability.

JSON representation

{
  "token": string,
  "tokenId": integer,
  "logProbability": number
}
CitationMetadata
A collection of source attributions for a piece of content.

Fields
citationSources[]
object (CitationSource)
Citations to sources for a specific response.

JSON representation

{
  "citationSources": [
    {
      object (CitationSource)
    }
  ]
}
CitationSource
A citation to a source for a portion of a specific response.

Fields
startIndex
integer
Optional. Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

endIndex
integer
Optional. End of the attributed segment, exclusive.

uri
string
Optional. URI that is attributed as a source for a portion of the text.

license
string
Optional. License for the GitHub project that is attributed as a source for segment.

License info is required for code citations.

JSON representation

{
  "startIndex": integer,
  "endIndex": integer,
  "uri": string,
  "license": string
}
GenerationConfig
Configuration options for model generation and outputs. Not all parameters are configurable for every model.

Fields
stopSequences[]
string
Optional. The set of character sequences (up to 5) that will stop output generation. If specified, the API will stop at the first appearance of a stop_sequence. The stop sequence will not be included as part of the response.

responseMimeType
string
Optional. MIME type of the generated candidate text. Supported MIME types are: text/plain: (default) Text output. application/json: JSON response in the response candidates. text/x.enum: ENUM as a string response in the response candidates. Refer to the docs for a list of all supported text MIME types.

responseSchema
object (Schema)
Optional. Output schema of the generated candidate text. Schemas must be a subset of the OpenAPI schema and can be objects, primitives or arrays.

If set, a compatible responseMimeType must also be set. Compatible MIME types: application/json: Schema for JSON response. Refer to the JSON text generation guide for more details.

candidateCount
integer
Optional. Number of generated responses to return.

Currently, this value can only be set to 1. If unset, this will default to 1.

maxOutputTokens
integer
Optional. The maximum number of tokens to include in a response candidate.

Note: The default value varies by model, see the Model.output_token_limit attribute of the Model returned from the getModel function.

temperature
number
Optional. Controls the randomness of the output.

Note: The default value varies by model, see the Model.temperature attribute of the Model returned from the getModel function.

Values can range from [0.0, 2.0].

topP
number
Optional. The maximum cumulative probability of tokens to consider when sampling.

The model uses combined Top-k and Top-p (nucleus) sampling.

Tokens are sorted based on their assigned probabilities so that only the most likely tokens are considered. Top-k sampling directly limits the maximum number of tokens to consider, while Nucleus sampling limits the number of tokens based on the cumulative probability.

Note: The default value varies by Model and is specified by theModel.top_p attribute returned from the getModel function. An empty topK attribute indicates that the model doesn't apply top-k sampling and doesn't allow setting topK on requests.

topK
integer
Optional. The maximum number of tokens to consider when sampling.

Gemini models use Top-p (nucleus) sampling or a combination of Top-k and nucleus sampling. Top-k sampling considers the set of topK most probable tokens. Models running with nucleus sampling don't allow topK setting.

Note: The default value varies by Model and is specified by theModel.top_p attribute returned from the getModel function. An empty topK attribute indicates that the model doesn't apply top-k sampling and doesn't allow setting topK on requests.

presencePenalty
number
Optional. Presence penalty applied to the next token's logprobs if the token has already been seen in the response.

This penalty is binary on/off and not dependant on the number of times the token is used (after the first). Use frequencyPenalty for a penalty that increases with each use.

A positive penalty will discourage the use of tokens that have already been used in the response, increasing the vocabulary.

A negative penalty will encourage the use of tokens that have already been used in the response, decreasing the vocabulary.

frequencyPenalty
number
Optional. Frequency penalty applied to the next token's logprobs, multiplied by the number of times each token has been seen in the respponse so far.

A positive penalty will discourage the use of tokens that have already been used, proportional to the number of times the token has been used: The more a token is used, the more dificult it is for the model to use that token again increasing the vocabulary of responses.

Caution: A negative penalty will encourage the model to reuse tokens proportional to the number of times the token has been used. Small negative values will reduce the vocabulary of a response. Larger negative values will cause the model to start repeating a common token until it hits the maxOutputTokens limit: "...the the the the the...".

responseLogprobs
boolean
Optional. If true, export the logprobs results in response.

logprobs
integer
Optional. Only valid if responseLogprobs=True. This sets the number of top logprobs to return at each decoding step in the Candidate.logprobs_result.

JSON representation

{
  "stopSequences": [
    string
  ],
  "responseMimeType": string,
  "responseSchema": {
    object (Schema)
  },
  "candidateCount": integer,
  "maxOutputTokens": integer,
  "temperature": number,
  "topP": number,
  "topK": integer,
  "presencePenalty": number,
  "frequencyPenalty": number,
  "responseLogprobs": boolean,
  "logprobs": integer
}
HarmCategory
The category of a rating.

These categories cover various kinds of harms that developers may wish to adjust.

Enums
HARM_CATEGORY_UNSPECIFIED	Category is unspecified.
HARM_CATEGORY_DEROGATORY	PaLM - Negative or harmful comments targeting identity and/or protected attribute.
HARM_CATEGORY_TOXICITY	PaLM - Content that is rude, disrespectful, or profane.
HARM_CATEGORY_VIOLENCE	PaLM - Describes scenarios depicting violence against an individual or group, or general descriptions of gore.
HARM_CATEGORY_SEXUAL	PaLM - Contains references to sexual acts or other lewd content.
HARM_CATEGORY_MEDICAL	PaLM - Promotes unchecked medical advice.
HARM_CATEGORY_DANGEROUS	PaLM - Dangerous content that promotes, facilitates, or encourages harmful acts.
HARM_CATEGORY_HARASSMENT	Gemini - Harassment content.
HARM_CATEGORY_HATE_SPEECH	Gemini - Hate speech and content.
HARM_CATEGORY_SEXUALLY_EXPLICIT	Gemini - Sexually explicit content.
HARM_CATEGORY_DANGEROUS_CONTENT	Gemini - Dangerous content.
HARM_CATEGORY_CIVIC_INTEGRITY	Gemini - Content that may be used to harm civic integrity.
SafetyRating
Safety rating for a piece of content.

The safety rating contains the category of harm and the harm probability level in that category for a piece of content. Content is classified for safety across a number of harm categories and the probability of the harm classification is included here.

Fields
category
enum (HarmCategory)
Required. The category for this rating.

probability
enum (HarmProbability)
Required. The probability of harm for this content.

blocked
boolean
Was this content blocked because of this rating?

JSON representation

{
  "category": enum (HarmCategory),
  "probability": enum (HarmProbability),
  "blocked": boolean
}
HarmProbability
The probability that a piece of content is harmful.

The classification system gives the probability of the content being unsafe. This does not indicate the severity of harm for a piece of content.

Enums
HARM_PROBABILITY_UNSPECIFIED	Probability is unspecified.
NEGLIGIBLE	Content has a negligible chance of being unsafe.
LOW	Content has a low chance of being unsafe.
MEDIUM	Content has a medium chance of being unsafe.
HIGH	Content has a high chance of being unsafe.
SafetySetting
Safety setting, affecting the safety-blocking behavior.

Passing a safety setting for a category changes the allowed probability that content is blocked.

Fields
category
enum (HarmCategory)
Required. The category for this setting.

threshold
enum (HarmBlockThreshold)
Required. Controls the probability threshold at which harm is blocked.

JSON representation

{
  "category": enum (HarmCategory),
  "threshold": enum (HarmBlockThreshold)
}
HarmBlockThreshold
Block at and beyond a specified harm probability.

Enums
HARM_BLOCK_THRESHOLD_UNSPECIFIED	Threshold is unspecified.
BLOCK_LOW_AND_ABOVE	Content with NEGLIGIBLE will be allowed.
BLOCK_MEDIUM_AND_ABOVE	Content with NEGLIGIBLE and LOW will be allowed.
BLOCK_ONLY_HIGH	Content with NEGLIGIBLE, LOW, and MEDIUM will be allowed.
BLOCK_NONE	All content will be allowed.
OFF	Turn off the safety filter.

## Files

Method: files.list
Lists the metadata for Files owned by the requesting project.

Endpoint
get
https://generativelanguage.googleapis.com/v1beta/files

Query parameters
pageSize
integer
Optional. Maximum number of Files to return per page. If unspecified, defaults to 10. Maximum pageSize is 100.

pageToken
string
Optional. A page token from a previous files.list call.

Request body
The request body must be empty.

Example request
Python
Node.js
Go
Shell

print("My files:")
for f in genai.list_files():
    print("  ", f.name)
Response body
Response for files.list.

If successful, the response body contains data with the following structure:

Fields
files[]
object (File)
The list of Files.

nextPageToken
string
A token that can be sent as a pageToken into a subsequent files.list call.

JSON representation

{
  "files": [
    {
      object (File)
    }
  ],
  "nextPageToken": string
}
Method: files.delete
Deletes the File.

Endpoint
delete
https://generativelanguage.googleapis.com/v1beta/{name=files/*}

Path parameters
name
string
Required. The name of the File to delete. Example: files/abc-123 It takes the form files/{file}.

Request body
The request body must be empty.

Example request
Python
Node.js
Go
Shell

myfile = genai.upload_file(media / "poem.txt")

myfile.delete()

try:
    # Error.
    model = genai.GenerativeModel("gemini-1.5-flash")
    result = model.generate_content([myfile, "Describe this file."])
except google.api_core.exceptions.PermissionDenied:
    pass
Response body
If successful, the response body is empty.

REST Resource: files
Resource: File
A file uploaded to the API.

Fields
name
string
Immutable. Identifier. The File resource name. The ID (name excluding the "files/" prefix) can contain up to 40 characters that are lowercase alphanumeric or dashes (-). The ID cannot start or end with a dash. If the name is empty on create, a unique name will be generated. Example: files/123-456

displayName
string
Optional. The human-readable display name for the File. The display name must be no more than 512 characters in length, including spaces. Example: "Welcome Image"

mimeType
string
Output only. MIME type of the file.

sizeBytes
string (int64 format)
Output only. Size of the file in bytes.

createTime
string (Timestamp format)
Output only. The timestamp of when the File was created.

A timestamp in RFC3339 UTC "Zulu" format, with nanosecond resolution and up to nine fractional digits. Examples: "2014-10-02T15:01:23Z" and "2014-10-02T15:01:23.045123456Z".

updateTime
string (Timestamp format)
Output only. The timestamp of when the File was last updated.

A timestamp in RFC3339 UTC "Zulu" format, with nanosecond resolution and up to nine fractional digits. Examples: "2014-10-02T15:01:23Z" and "2014-10-02T15:01:23.045123456Z".

expirationTime
string (Timestamp format)
Output only. The timestamp of when the File will be deleted. Only set if the File is scheduled to expire.

A timestamp in RFC3339 UTC "Zulu" format, with nanosecond resolution and up to nine fractional digits. Examples: "2014-10-02T15:01:23Z" and "2014-10-02T15:01:23.045123456Z".

sha256Hash
string (bytes format)
Output only. SHA-256 hash of the uploaded bytes.

A base64-encoded string.

uri
string
Output only. The uri of the File.

state
enum (State)
Output only. Processing state of the File.

error
object (Status)
Output only. Error status if File processing failed.

Union field
metadata
. Metadata for the File.
metadata
can be only one of the following:
videoMetadata
object (VideoMetadata)
Output only. Metadata for a video.

JSON representation

{
  "name": string,
  "displayName": string,
  "mimeType": string,
  "sizeBytes": string,
  "createTime": string,
  "updateTime": string,
  "expirationTime": string,
  "sha256Hash": string,
  "uri": string,
  "state": enum (State),
  "error": {
    object (Status)
  },

  // Union field metadata can be only one of the following:
  "videoMetadata": {
    object (VideoMetadata)
  }
  // End of list of possible types for union field metadata.
}
VideoMetadata
Metadata for a video File.

Fields
videoDuration
string (Duration format)
Duration of the video.

A duration in seconds with up to nine fractional digits, ending with 's'. Example: "3.5s".

JSON representation

{
  "videoDuration": string
}
State
States for the lifecycle of a File.

Enums
STATE_UNSPECIFIED	The default value. This value is used if the state is omitted.
PROCESSING	File is being processed and cannot be used for inference yet.
ACTIVE	File is processed and available for inference.
FAILED	File failed processing.
Status
The Status type defines a logical error model that is suitable for different programming environments, including REST APIs and RPC APIs. It is used by gRPC. Each Status message contains three pieces of data: error code, error message, and error details.

You can find out more about this error model and how to work with it in the API Design Guide.

Fields
code
integer
The status code, which should be an enum value of google.rpc.Code.

message
string
A developer-facing error message, which should be in English. Any user-facing error message should be localized and sent in the google.rpc.Status.details field, or localized by the client.

details[]
object
A list of messages that carry the error details. There is a common set of message types for APIs to use.

An object containing fields of an arbitrary type. An additional field "@type" contains a URI identifying the type. Example: { "id": 1234, "@type": "types.example.com/standard/id" }.

JSON representation

{
  "code": integer,
  "message": string,
  "details": [
    {
      "@type": string,
      field1: ...,
      ...
    }
  ]
}